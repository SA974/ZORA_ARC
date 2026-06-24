"""Validation Lot 3 : runner idempotent, preflight ingestion, /health enrichi."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.document_ingestion import ingest_folder
from app.services.provider_health import check_ollama

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# 3b preflight : dossier vide, dry_run=False -> preflight Ollama doit passer, 0 fichier, 0 écriture
with tempfile.TemporaryDirectory() as d:
    summary = ingest_folder(d, dry_run=False)
    check("Lot3-preflight OK (Ollama up) sur dossier vide",
          summary.get("status") != "provider_unhealthy" and summary.get("total_found") == 0,
          f"status={summary.get('status')}")

# 3b preflight négatif simulé : embedder factice cassé -> ingest_folder court-circuite proprement
import app.services.document_ingestion as di


class _BadEmbedder:
    class settings:
        embedding_model = "x"
        embedding_dim = 768

    def configured(self):
        return False


orig = di.get_embedder
di.get_embedder = lambda: _BadEmbedder()
try:
    with tempfile.TemporaryDirectory() as d:
        s = ingest_folder(d, dry_run=False)
    check("Lot3-preflight court-circuite si embedder KO",
          s.get("status") == "provider_unhealthy" and s.get("ok") is False, f"status={s.get('status')}")
finally:
    di.get_embedder = orig

# 3 /health : section ollama présente et joignable
h = check_ollama()
check("Lot3 check_ollama joignable + modèle présent", h.get("ok") and h.get("model_present"),
      f"reachable={h.get('reachable')} present={h.get('model_present')}")

print("\n=== VALIDATION LOT 3 ===")
n = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
print(f"\n{n}/{len(results)} PASS")
sys.exit(0 if n == len(results) else 1)
