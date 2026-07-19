"""
Offline sanity check for the harness: no real NVIDIA API calls. Scripts a
fake OpenAI-shaped client so we can verify agent_loader parsing, the
tools.py tool-execution path (including an actual tool call), and the
orchestrator/coder/reviewer loop control flow (task parsing, verdict
parsing, ALL_DONE termination) all work end to end before you spend NIM
credits on it.

Run: python test_smoke.py
"""
import json
from pathlib import Path
from types import SimpleNamespace

import sdlc_tools as tools  # renamed from tools.py to avoid shadowing PaddleOCR's `tools` package
from agent_loader import load_agents_dir
from nim_client import run_agent_turn

PROJECT_ROOT = Path(__file__).parent / "testproj"
tools.PROJECT_ROOT = PROJECT_ROOT


class FakeToolCall:
    def __init__(self, call_id, name, arguments: dict):
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))

    def model_dump(self):
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


class FakeMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeClient:
    """Returns scripted responses in order, one per .create() call,
    regardless of `model` or `messages` passed in."""

    def __init__(self, script: list[FakeMessage]):
        self._script = list(script)
        self._i = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        msg = self._script[self._i]
        self._i += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def run_check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, f"FAILED: {label}"


def main():
    print("== 1. agent_loader parses the three real subagent files ==")
    agents = load_agents_dir(PROJECT_ROOT / ".claude" / "agents")
    run_check("all three agents loaded", set(agents) == {"orchestrator", "coder", "reviewer"})
    run_check("orchestrator tools parsed", "Agent(coder, reviewer)" in agents["orchestrator"].tools)
    run_check("coder has Bash", "Bash" in agents["coder"].tools)
    run_check("reviewer has no Write/Edit", not ({"Write", "Edit"} & set(agents["reviewer"].tools)))

    print("\n== 2. tools.resolve_tools maps Claude tool names correctly ==")
    coder_schemas, coder_impls = tools.resolve_tools(agents["coder"].tools)
    run_check("coder gets write_file impl", "write_file" in coder_impls)
    run_check("coder gets run_bash impl", "run_bash" in coder_impls)
    reviewer_schemas, reviewer_impls = tools.resolve_tools(agents["reviewer"].tools)
    run_check("reviewer does NOT get write_file", "write_file" not in reviewer_impls)
    run_check("reviewer gets read_file", "read_file" in reviewer_impls)

    print("\n== 3. run_agent_turn executes a real tool call end-to-end ==")
    script = [
        FakeMessage(
            content="",
            tool_calls=[
                FakeToolCall(
                    "call_1", "write_file",
                    {"path": "PLAN/smoke_test.txt", "content": "hello from fake coder"},
                )
            ],
        ),
        FakeMessage(content="Done. Wrote PLAN/smoke_test.txt.", tool_calls=None),
    ]
    fake_client = FakeClient(script)
    final_text, history = run_agent_turn(
        fake_client, "fake-model", "You are a test coder.", "write a test file",
        coder_schemas, coder_impls, verbose=True,
    )
    run_check("final text returned after tool call", final_text == "Done. Wrote PLAN/smoke_test.txt.")
    written = PROJECT_ROOT / "PLAN" / "smoke_test.txt"
    run_check("tool call actually wrote the file", written.read_text() == "hello from fake coder")
    run_check("tool result fed back into message history", any(m.get("role") == "tool" for m in history))

    print("\n== 4. Full orchestrator/coder/reviewer loop control flow (mocked) ==")
    import re
    from run_sdlc import TASK_RE, ALL_DONE_RE, VERDICT_RE

    orch_turn_1 = "```task\nWrite a hello-world function.\n```"
    task_match = TASK_RE.search(orch_turn_1)
    run_check("TASK_RE extracts task block", task_match and task_match.group(1).strip() == "Write a hello-world function.")

    reviewer_reply = "VERDICT: PASS\n\nCritical:\n- none\n"
    v = VERDICT_RE.search(reviewer_reply)
    run_check("VERDICT_RE parses PASS", v and v.group(1).upper() == "PASS")

    orch_turn_2 = "All tasks complete.\n<ALL_DONE/>"
    run_check("ALL_DONE_RE detects completion", bool(ALL_DONE_RE.search(orch_turn_2)))

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
