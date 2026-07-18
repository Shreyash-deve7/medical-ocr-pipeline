import re
from pathlib import Path

file_path = Path(r'c:\Users\oliad\Desktop\intern-ocr-paddleocr-aditya\pipeline_v1\run_sdlc.py')
content = file_path.read_text(encoding='utf-8')

# Replace protocol addendum using regex
pattern = r'ORCHESTRATOR_PROTOCOL_ADDENDUM = """.*?"""'
replacement = '''ORCHESTRATOR_PROTOCOL_ADDENDUM = """
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
 """'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

file_path.write_text(content, encoding='utf-8')
print('Protocol updated')
