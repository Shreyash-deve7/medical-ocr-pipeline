"""
Simulates the Claude Code orchestrator/coder/reviewer subagent loop on top
of the NVIDIA NIM API, reusing your existing .claude/agents/*.md files
as-is.

Key difference from real Claude Code subagents: there's no `Agent` tool for
the orchestrator model to call to "spawn" the coder/reviewer. Instead this
script IS the orchestration — it calls the orchestrator model to decide the
next task, then directly runs a fresh coder turn and a fresh reviewer turn
in Python, and feeds the reviewer's verdict back to the orchestrator on the
next loop iteration. Each of the three roles still gets its own isolated,
fresh conversation per spawn, same as real subagents — nothing is shared
between them except what this script explicitly passes along.

Usage:
    python run_sdlc.py --goal "Implement the GPU executor pattern from
        goal.md" --project-root ../

    python run_sdlc.py --goal-file goal.md --project-root ../ \
        --orchestrator-model stepfun-ai/step-3.7-flash \
        --coder-model stepfun-ai/step-3.7-flash \
        --reviewer-model stepfun-ai/step-3.7-flash

Check https://build.nvidia.com for current model IDs — the catalog changes.
Pick models documented to support tool/function calling; not all NIM models
do.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from dotenv import load_dotenv

import tools
from agent_loader import load_agents_dir
from nim_client import get_client, run_agent_turn

TASK_RE = re.compile(r"```task\s*\n(.*?)```", re.DOTALL)
ALL_DONE_RE = re.compile(r"<ALL_DONE\s*/?>", re.IGNORECASE)
ASK_USER_RE = re.compile(r"<ASK_USER>(.*?)</ASK_USER>", re.DOTALL | re.IGNORECASE)
VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|CONDITIONAL|FAIL)", re.IGNORECASE)

# Appended to the orchestrator's own system prompt. Its .md file assumes a
# real `Agent` tool exists to spawn coder/reviewer — that tool doesn't exist
# here, so it needs a different, parseable way to hand off a task to this
# script instead.
ORCHESTRATOR_PROTOCOL_ADDENDUM = """
 ## Simulation protocol — FOLLOW THIS EXACTLY
 You have no ability to spawn the coder or reviewer subagents yourself. A Python script drives the loop: it calls you once per iteration, runs the coder, runs the reviewer, then calls you again. Your ONLY job each turn is to emit ONE of the three outputs below and then stop.

 ### STRICT reading budget: 3 tool calls maximum per turn
 You may call read_file, grep_files, or glob_files AT MOST 3 times total per turn. After 3 file reads — or if PLAN/sdlc_state.md does not exist yet — STOP reading and emit your decision immediately. Do NOT read the same file more than once. Do NOT scan the entire codebase; the goal is already in your context.

 ### Your three legal outputs (emit exactly one, then stop)
 OUTPUT A — next task for the coder:
 ```task
 <specific, scoped instructions: which file(s) to change, what to do, acceptance criteria — all self-contained so the coder needs nothing else>
 ```
 OUTPUT B — all tasks complete: <ALL_DONE/>
 OUTPUT C — need user input: <ASK_USER>one specific question</ASK_USER>

 ### First iteration rule (no state file exists yet)
 Do NOT spend reads looking for PLAN/sdlc_state.md — it does not exist. Instead:
 1) write the task list to PLAN/sdlc_state.md in one write_file call,
 2) immediately emit OUTPUT A for the first task.
 Total tool calls: 1.

 ### Hard stop rule
 If you have made 3 or more tool calls this turn and still have not emitted a task block: stop all tool calls NOW and emit your best OUTPUT A. An imperfect task the coder can refine is better than a task that never gets issued.
 """


def build_orchestrator_user_message(goal: str, last_report: str, iteration: int) -> str:
    return (
        f"GOAL:\n{goal}\n\n"
        f"ITERATION: {iteration}\n\n"
        f"MOST RECENT REVIEWER REPORT (or '(none yet)' on the first turn):\n"
        f"{last_report}\n\n"
        "Decide the next step per the simulation protocol. Remember: 3 tool "
        "calls maximum this turn, then emit your task block. On iteration 1 "
        "write PLAN/sdlc_state.md in one call and immediately emit task 1."
    )


def main():
    parser = argparse.ArgumentParser(description="Simulated orchestrator/coder/reviewer SDLC loop on NVIDIA NIM")
    parser.add_argument("--agents-dir", default=".claude/agents", help="Path to your orchestrator.md/coder.md/reviewer.md")
    parser.add_argument("--project-root", default=".", help="Root directory the coder/reviewer's file tools operate on")
    parser.add_argument("--goal", default=None, help="The goal, as a string")
    parser.add_argument("--goal-file", default=None, help="Path to a file containing the goal (e.g. an architecture doc)")
    parser.add_argument("--orchestrator-model", default="stepfun-ai/step-3.7-flash")
    parser.add_argument("--coder-model", default="stepfun-ai/step-3.7-flash")
    parser.add_argument("--reviewer-model", default="stepfun-ai/step-3.7-flash")
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--max-retries-per-task", type=int, default=3)
    parser.add_argument("--orchestrator-tool-iters", type=int, default=5, help="Max tool calls the orchestrator can make per turn before "
        "we force-extract its best task and continue (default: 5)")
    parser.add_argument("--agent-tool-iters", type=int, default=15, help="Max tool calls coder/reviewer can make per turn (default: 15)")

    load_dotenv()
    load_dotenv("sdlc_sim/.env")
    args = parser.parse_args()

    if not args.goal and not args.goal_file:
        parser.error("Pass --goal \"...\" or --goal-file path/to/goal.md")
    goal = args.goal or Path(args.goal_file).read_text(encoding="utf-8")

    tools.PROJECT_ROOT = Path(args.project_root).resolve()
    print(f"Project root: {tools.PROJECT_ROOT}")

    agents = load_agents_dir(args.agents_dir)
    for required in ("orchestrator", "coder", "reviewer"):
        if required not in agents:
            raise SystemExit(
                f"Missing '{required}' agent in {args.agents_dir} "
                f"(found: {list(agents.keys())})"
            )

    orch_cfg, coder_cfg, reviewer_cfg = agents["orchestrator"], agents["coder"], agents["reviewer"]

    orch_tools, orch_impls = tools.resolve_tools(orch_cfg.tools)
    coder_tools, coder_impls = tools.resolve_tools(coder_cfg.tools)
    reviewer_tools, reviewer_impls = tools.resolve_tools(reviewer_cfg.tools)

    client = get_client()

    last_report = "(none yet — this is the first task)"
    fail_streak = 0

    for iteration in range(1, args.max_iterations + 1):
        print(f"\n{'='*70}\nORCHESTRATOR — iteration {iteration}\n{'='*70}")
        orch_user_msg = build_orchestrator_user_message(goal, last_report, iteration)
        orch_text, _ = run_agent_turn(
            client, args.orchestrator_model,
            orch_cfg.system_prompt + ORCHESTRATOR_PROTOCOL_ADDENDUM,
            orch_user_msg, orch_tools, orch_impls,
        )
        print(orch_text)

        if ALL_DONE_RE.search(orch_text):
            print("\nOrchestrator declared the goal complete. Stopping.")
            break

        ask_match = ASK_USER_RE.search(orch_text)
        if ask_match:
            print(f"\nOrchestrator is asking you: {ask_match.group(1).strip()}")
            reply = input("Your answer: ")
            goal += f"\n\n[User clarification, iteration {iteration}]: {reply}"
            continue

        task_match = TASK_RE.search(orch_text)
        if not task_match:
            print(
                "\nWARNING: orchestrator didn't emit a ```task block, <ALL_DONE/>, "
                "or <ASK_USER>. Using its full reply as the task instructions — "
                "if this keeps happening, the model may need a stronger nudge "
                "or a different model for the orchestrator role."
            )
            task_text = orch_text.strip()
        else:
            task_text = task_match.group(1).strip()

        print(f"\n{'='*70}\nCODER — iteration {iteration}\n{'='*70}")
        coder_text, _ = run_agent_turn(
            client, args.coder_model, coder_cfg.system_prompt,
            task_text, coder_tools, coder_impls,
        )
        print(coder_text)

        print(f"\n{'='*70}\nREVIEWER — iteration {iteration}\n{'='*70}")
        reviewer_user_msg = (
            f"Original instructions given to the coder:\n{task_text}\n\n"
            f"Coder's report of what it did:\n{coder_text}"
        )
        reviewer_text, _ = run_agent_turn(
            client, args.reviewer_model, reviewer_cfg.system_prompt,
            reviewer_user_msg, reviewer_tools, reviewer_impls,
        )
        print(reviewer_text)

        verdict_match = VERDICT_RE.search(reviewer_text)
        verdict = verdict_match.group(1).upper() if verdict_match else "UNKNOWN"
        print(f"\n--> Verdict: {verdict}")

        fail_streak = 0 if verdict == "PASS" else fail_streak + 1

        last_report = (
            f"Task instructions were:\n{task_text}\n\n"
            f"Coder reported:\n{coder_text}\n\n"
            f"Reviewer verdict: {verdict}\nFull reviewer report:\n{reviewer_text}"
        )

        if verdict != "PASS" and fail_streak >= args.max_retries_per_task:
            print(
                f"\nThis task failed review {fail_streak} times in a row. "
                "Stopping for human input rather than looping indefinitely."
            )
            break
    else:
        print(f"\nHit --max-iterations ({args.max_iterations}) without the orchestrator declaring done.")

    print("\nRun ended.")


if __name__ == "__main__":
    main()
