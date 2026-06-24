#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from app.db import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM zora.documents")
    row = cur.fetchone()
    print(f"Total documents: {row['cnt'] if row else 'NULL'}")
except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        conn.close()
