from __future__ import annotations

from typing import Any

from app.models.schemas import TaskCard


MODULES = {
    "M1": "PARA",
    "M2": "resume_progressif",
    "M3": "pensee_complexe",
    "M4": "registre_preuves",
    "M5": "conformite",
    "M6": "scientifique",
    "M7": "spatial",
    "M8": "documentaire_rag",
}


class ZoraArcService:
    def build_taskcard(self, query: str, evidence_level: str = "standard") -> TaskCard:
        return TaskCard(
            title=f"Retrieve context for: {query[:80]}",
            objective="Construire un paquet de contexte vérifiable, pas une réponse finale longue.",
            central_question=query,
            expected_deliverable="ContextBundle structuré avec sources, faits, passages, citations et warnings.",
            provided_data=[query],
            constraints=[
                "Ne pas confondre Hindsight et MemGraphRAG.",
                "Ne pas exposer de secret.",
                "Préserver la provenance documentaire.",
            ],
            expected_evidence_level=evidence_level,
        )

    def score_router(self, query: str, evidence_level: str = "standard") -> dict[str, Any]:
        q = query.lower()
        signals = {
            "Ct": 2 if len(query) > 180 else 1,
            "Cs": 2 if any(word in q for word in ("preuve", "citation", "source", "audit")) else 1,
            "Rk": 2 if any(word in q for word in ("sécurité", "secret", "risque", "compliance")) else 1,
            "Ex": 2 if any(word in q for word in ("scientifique", "postgis", "pgvector", "architecture")) else 1,
            "Op": 2 if any(word in q for word in ("migration", "ingestion", "production")) else 1,
            "Tp": 2 if evidence_level in ("renforce", "critique") else 1,
        }
        score = sum(signals.values())
        if evidence_level == "critique" or score >= 11:
            level = "critique"
        elif evidence_level == "renforce" or score >= 9:
            level = "renforce"
        elif score >= 7:
            level = "standard"
        else:
            level = "leger"
        modules = ["M1", "M4", "M5", "M8"]
        if "postgis" in q or "spatial" in q:
            modules.append("M7")
        if "scientifique" in q:
            modules.append("M6")
        return {"signals": signals, "SR": score, "level": level, "modules": {key: MODULES[key] for key in modules}}

    def audit_answer(self, payload: dict[str, Any]) -> dict[str, Any]:
        findings: list[str] = []
        if not payload.get("sources"):
            findings.append("missing_sources")
        if not payload.get("citations"):
            findings.append("missing_citations")
        if not payload.get("limits"):
            findings.append("missing_limits")
        if not payload.get("risks"):
            findings.append("missing_risks")
        return {"ok": not findings, "findings": findings}
