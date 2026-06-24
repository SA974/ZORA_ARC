#!/usr/bin/env python
import psycopg2
from datetime import datetime

try:
    conn = psycopg2.connect(
        host='localhost',
        database='rag_arc',
        user='postgres',
        password='postgres',
        port=5432
    )
    cursor = conn.cursor()

    # Voir quand les documents ont été créés
    cursor.execute("""
    SELECT
      COUNT(*) as total,
      MIN(CAST(metadata->>'ingested_at' AS TIMESTAMP)) as earliest,
      MAX(CAST(metadata->>'ingested_at' AS TIMESTAMP)) as latest
    FROM zora.documents
    WHERE metadata->>'ingested_at' IS NOT NULL
    """)
    row = cursor.fetchone()
    total, earliest, latest = row

    print("=" * 60)
    print("TIMELINE INGESTION")
    print("=" * 60)
    print("\nDocuments avec timestamp:")
    print("  Total: " + str(total))
    if earliest:
        print("  Premiere ingestion: " + str(earliest))
    if latest:
        print("  Derniere ingestion: " + str(latest))

    # Voir la distribution par jour
    cursor.execute("""
    SELECT
      DATE(CAST(metadata->>'ingested_at' AS TIMESTAMP)) as day,
      COUNT(*) as count
    FROM zora.documents
    WHERE metadata->>'ingested_at' IS NOT NULL
    GROUP BY DATE(CAST(metadata->>'ingested_at' AS TIMESTAMP))
    ORDER BY day DESC
    """)
    rows = cursor.fetchall()

    if rows:
        print("\nDistribution par jour:")
        for day, count in rows:
            print("  " + str(day) + ": " + str(count) + " docs")

    print("\n" + "=" * 60)

    cursor.close()
    conn.close()

except Exception as e:
    print("ERROR: " + str(e))
