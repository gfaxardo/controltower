"""Execute driver_serving_facts_build.sql step by step."""
import sys, re; sys.path.insert(0, '.')
from app.db.connection import get_db

with open('sql/driver_serving_facts_build.sql', 'r') as f:
    sql = f.read()

# Split by semicolon OUTSIDE of quotes/parens (naive but works for this SQL)
statements = [s.strip() for s in sql.split(';') if s.strip()]

print(f'Executing {len(statements)} statements...')
with get_db() as conn:
    cur = conn.cursor()
    ok = 0; fail = 0
    for i, stmt in enumerate(statements):
        try:
            cur.execute(stmt)
            msg = 'OK'
            if 'CREATE MATERIALIZED VIEW' in stmt:
                msg = 'MV CREATED'
            elif 'CREATE INDEX' in stmt:
                msg = 'INDEX OK'
            print(f'  [{i}] {msg}')
            ok += 1
        except Exception as e:
            print(f'  [{i}] FAILED: {str(e)[:200]}')
            fail += 1
            conn.rollback()
    conn.commit()
print(f'\nDone: {ok} OK, {fail} FAILED')
