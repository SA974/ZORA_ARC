from __future__ import annotations

from dataclasses import dataclass


HMEM_LEVELS = ("domain", "theme", "subtheme", "entity", "fact", "passage")


@dataclass(frozen=True)
class RouteStep:
    level: str
    label: str
    score: float


class HMemRouter:
    def route_query(self, query: str) -> list[dict[str, object]]:
        normalized = " ".join(query.lower().split())
        tokens = [token.strip(".,;:!?()[]") for token in normalized.split() if token.strip()]
        theme = "general"
        if any(token in tokens for token in ("postgis", "spatial", "geo", "geospatial")):
            theme = "spatial"
        elif any(token in tokens for token in ("hindsight", "memory", "mémoire", "agentique")):
            theme = "agentic_memory"
        elif any(token in tokens for token in ("rag", "document", "citation", "evidence", "preuve")):
            theme = "documentary_rag"
        elif any(token in tokens for token in ("postgres", "pgvector", "vector")):
            theme = "postgres_vector"

        steps = [
            RouteStep("domain", "arc_mem", 1.0),
            RouteStep("theme", theme, 0.9),
            RouteStep("subtheme", "_".join(tokens[:4]) if tokens else "unspecified", 0.6),
        ]
        if tokens:
            steps.append(RouteStep("entity", tokens[0], 0.4))
        steps.extend([RouteStep("fact", "candidate_facts", 0.3), RouteStep("passage", "candidate_passages", 0.2)])
        return [step.__dict__ for step in steps]
