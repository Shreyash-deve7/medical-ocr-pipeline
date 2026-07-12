import sys
sys.path.insert(0, '.')
from main import get_db
conn = get_db()
rows = conn.execute("SELECT * FROM providers WHERE kind='ocr'").fetchall()
for r in rows:
    print(dict(r))
conn.close()