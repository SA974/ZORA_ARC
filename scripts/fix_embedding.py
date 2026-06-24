#!/usr/bin/env python3
"""Truncate zora tables to allow schema migration."""

from app.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("TRUNCATE TABLE zora.chunks CASCADE")
cur.execute("TRUNCATE TABLE zora.documents CASCADE")
conn.commit()
print("✓ Truncated zora tables")
conn.close()
