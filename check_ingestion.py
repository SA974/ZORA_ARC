#!/usr/bin/env python
import psycopg2

try:
    conn = psycopg2.connect(
        host='localhost',
        database='rag_arc',
        user='postgres',
        password='postgres',
        port=5432
    )
    cursor = conn.cursor()

    # État documents zora
    cursor.execute("""
    SELECT
      COUNT(*) AS total,
      COUNT(CASE WHEN content_hash IS NOT NULL THEN 1 END) AS with_hash,
      COUNT(CASE WHEN metadata IS NOT NULL THEN 1 END) AS with_meta
    FROM zora.documents
    """)
    doc_row = cursor.fetchone()
    doc_total, doc_hash, doc_meta = doc_row

    # État chunks zora
    cursor.execute("""
    SELECT
      COUNT(*) AS total,
      COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) AS with_emb,
      COUNT(DISTINCT document_id) AS unique_docs
    FROM zora.chunks
    """)
    chunk_row = cursor.fetchone()
    chunk_total, chunk_emb, chunk_unique = chunk_row

    print("=" * 60)
    print("INGESTION PDF - BILAN DETAILLE")
    print("=" * 60)
    print("\n[ZORA DOCUMENTS - schema unifie]")
    print("  Total documents: " + str(doc_total))
    print("  Avec content_hash: " + str(doc_hash))
    print("  Avec metadata: " + str(doc_meta))

    print("\n[ZORA CHUNKS]")
    print("  Total chunks: " + str(chunk_total))
    print("  Avec embeddings: " + str(chunk_emb))
    print("  Documents uniques: " + str(chunk_unique))

    if chunk_total > 0:
        pct = (chunk_emb * 100.0) / chunk_total
        print("  Couverture embedding: " + str(round(pct, 1)) + "%")

    if chunk_total > 0 and chunk_emb < chunk_total:
        orphans = chunk_total - chunk_emb
        print("  [WARNING] Chunks sans embedding: " + str(orphans))

    print("\n" + "=" * 60)

    cursor.close()
    conn.close()

except Exception as e:
    print("ERROR: " + str(e))
