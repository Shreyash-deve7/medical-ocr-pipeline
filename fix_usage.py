from pathlib import Path

file_path = Path(r'c:\Users\oliad\Desktop\intern-ocr-paddleocr-aditya\pipeline_v1\run_sdlc.py')
lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)

# Find and replace the usage section
for i, line in enumerate(lines):
    if 'Usage: python run_sdlc.py --goal' in line and 'MedVault' in line:
        lines[i] = 'Usage: python run_sdlc.py --goal "Implement the GPU executor pattern from goal.md" --project-root ../\n'
    if '--orchestrator-model meta/llama-3.3-70b-instruct' in line:
        lines[i] = '--orchestrator-model stepfun-ai/step-3.7-flash \\\n'
    if '--coder-model qwen/qwen2.5-coder-32b-instruct' in line:
        lines[i] = '--coder-model stepfun-ai/step-3.7-flash \\\n'
    if '--reviewer-model meta/llama-3.3-70b-instruct' in line and 'llama' in line:
        lines[i] = '--reviewer-model stepfun-ai/step-3.7-flash\n'

file_path.write_text(''.join(lines), encoding='utf-8')
print('Usage section updated')
