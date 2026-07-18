# SDLC loop simulator (NVIDIA NIM edition)

Runs the same orchestrator → coder → reviewer loop as the Claude Code
subagent setup, but on top of the NVIDIA NIM OpenAI-compatible API instead
of Claude Code itself. Reuses your existing `.claude/agents/orchestrator.md`,
`coder.md`, and `reviewer.md` files unmodified — it parses their frontmatter
and system prompts directly.

## What's different from real Claude Code subagents

- **No `Agent` tool.** The orchestrator can't spawn coder/reviewer itself —
  this script does that in Python instead. The orchestrator's job each turn
  is just to decide *what* the next coder task is, using a small text
  protocol (see below), and this script does the actual dispatch.
- **No automatic skill preloading.** `reviewer.md`'s `skills:` frontmatter
  (`code-reviewer`, `playwright-expert`) is ignored by this harness — Claude
  Code's skill-loading mechanism doesn't exist here. If you want the
  reviewer to follow those skills' checklists, paste their content into
  `reviewer.md`'s system prompt body directly, or into the goal text.
- **No persistent memory directory** — `memory: project` in the frontmatter
  is likewise ignored. State only persists via whatever files the agents
  write (e.g. `PLAN/sdlc_state.md`), same as any other file in your repo.
- **Tool calling quality depends on the NIM model you pick.** Not every
  model in NVIDIA's catalog supports function calling reliably. Models
  documented to support it well as of writing: `meta/llama-3.3-70b-instruct`,
  `meta/llama-3.1-70b-instruct`. Check https://build.nvidia.com for the
  current catalog before relying on a specific model — it changes.

## Setup

```bash
cd sdlc_sim
pip install -r requirements.txt
cp .env.example .env
# edit .env, paste your nvapi-... key
```

Make sure your actual project has the three agent files at
`.claude/agents/orchestrator.md`, `coder.md`, `reviewer.md` (the ones you
already placed).

## Run it

```bash
python run_sdlc.py \
  --agents-dir /path/to/your/project/.claude/agents \
  --project-root /path/to/your/project \
  --goal-file /path/to/MedVault_Pipeline_Architecture_Proposal.md \
  --orchestrator-model meta/llama-3.3-70b-instruct \
  --coder-model meta/llama-3.3-70b-instruct \
  --reviewer-model meta/llama-3.3-70b-instruct
```

Or with a plain string goal instead of a file:

```bash
python run_sdlc.py --goal "Add the GPU executor pattern to gpu_manager.py" \
  --project-root /path/to/your/project
```

`--project-root` is the sandbox boundary for the coder/reviewer's file
tools (`read_file`/`write_file`/`edit_file`/`grep_files`/`glob_files` all
resolve paths relative to it, and refuse to escape it). `run_bash` runs
inside that directory too, though as noted in `tools.py`, bash itself can
still reach outside it — this is a simulation harness, not a sandbox, so
only point it at a project you trust the model with.

## How the loop works

1. **Orchestrator turn** — gets the goal + the last reviewer report (or
   "none yet" on turn one), decides the next step, and must respond with
   exactly one of:
   - a ` ```task ` fenced block with instructions for the coder
   - `<ALL_DONE/>` if everything's finished
   - `<ASK_USER>question</ASK_USER>` if it needs your input — the script
     will prompt you on the terminal and feed your answer back in
2. **Coder turn** — fresh conversation, gets only the task text, has
   Read/Write/Edit/Bash/Grep/Glob per its frontmatter, implements it, and
   reports back.
3. **Reviewer turn** — fresh conversation, gets the task instructions +
   the coder's report, has Read/Grep/Glob/Bash (no Write/Edit — enforced
   by `tools.resolve_tools`, not just by the prompt), and must end its
   reply with `VERDICT: PASS`, `VERDICT: CONDITIONAL`, or `VERDICT: FAIL`.
4. Verdict feeds back into the orchestrator's next turn. `PASS` → next
   task. `FAIL`/`CONDITIONAL` → orchestrator re-instructs the coder on the
   same task. Three failed reviews in a row on the same task stops the run
   so you can look at it, rather than looping forever.

## Before you point it at a real project

Run `python test_smoke.py` first — it uses a scripted fake client (no
network calls, no API credits spent) to verify your three `.md` files
parse correctly, tool permissions resolve the way you expect (e.g. the
reviewer genuinely can't call `write_file`), and the task/verdict/done
parsing logic works, before you spend NIM credits on a live run.

## Known rough edges to watch for

- **Small/instruction-light models will drift from the text protocol.**
  If the orchestrator stops reliably emitting ` ```task ` blocks or
  `<ALL_DONE/>`, the script falls back to treating its whole reply as the
  task (with a warning printed) — check the output when you see that
  warning, it usually means the model needs a stronger system-prompt nudge
  or a swap to a more capable model for that role specifically.
- **`edit_file` requires an exact, unique match**, same restriction as
  Claude Code's real `Edit` tool. If the coder's `old_str` doesn't match
  verbatim (whitespace included), it gets an error back and has to retry
  with more context — that's intentional, not a bug, but weaker models may
  need a few attempts.
- **No conversation memory between spawns**, by design — if the coder needs
  context from a previous task, the orchestrator has to explicitly restate
  it in the next task block, same rule as in `orchestrator.md`'s own
  instructions.
