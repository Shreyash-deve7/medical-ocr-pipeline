from pathlib import Path

file_path = Path(r'c:\Users\oliad\Desktop\intern-ocr-paddleocr-aditya\pipeline_v1\run_sdlc.py')
content = file_path.read_text(encoding='utf-8')

# Fix the indentation issue
content = content.replace(
    '"calls maximum this turn, then emit your task block. On iteration 1 "\n"write PLAN/sdlc_state.md in one call and immediately emit task 1."',
    '"calls maximum this turn, then emit your task block. On iteration 1 "\n        "write PLAN/sdlc_state.md in one call and immediately emit task 1."'
)

file_path.write_text(content, encoding='utf-8')
print('Done')