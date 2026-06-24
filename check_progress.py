#!/usr/bin/env python
import psycopg
from datetime import datetime, timedelta

try:
    conn = psycopg.connect(
        host='localhost',
        dbname='rag_arc',
        user='postgres',
        password='postgres',
        port=5432
    )
    cursor = conn.cursor()

    # Docs ingérés MAINTENANT
    cursor.execute("""
    SELECT
      COUNT(*) as total,
      MAX(CAST(metadata->>'ingested_at' AS TIMESTAMP)) as last_ingested
    FROM zora.documents
    """)
    total, last_ingested = cursor.fetchone()

    # Chunks actuels
    cursor.execute("SELECT COUNT(*) FROM zora.chunks")
    chunks = cursor.fetchone()[0]

    print("=" * 60)
    print("PROGRESSION INGESTION EN DIRECT")
    print("=" * 60)
    print("\nDocuments ingérés: " + str(total))
    print("Chunks créés: " + str(chunks))
    if last_ingested:
        print("Dernier document: " + str(last_ingested))

    # Progression estimée
    initial = 4897
    current = total
    added = current - initial
    print("\nAjoutés cette session: " + str(added) + " docs")

    if added > 0:
        start_time = datetime(2026, 6, 18, 16, 23)
        elapsed = datetime.now() - start_time
        rate = added / elapsed.total_seconds() * 3600
        remaining = 16670 - current
        eta_hours = remaining / rate if rate > 0 else 0
        print("Vitesse: " + str(round(rate, 1)) + " docs/heure")
        print("Temps écoulé: " + str(int(elapsed.total_seconds() / 60)) + " min")
        print("Docs restants: " + str(remaining))
        print("ETA: " + str(int(eta_hours)) + "h " + str(int((eta_hours % 1) * 60)) + "min")

    print("\n" + "=" * 60)

    cursor.close()
    conn.close()

except Exception as e:
    print("ERROR: " + str(e))
