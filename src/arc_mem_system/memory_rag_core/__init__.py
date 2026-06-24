"""Bloc ``memory_rag_core`` — H-MEM (mémoire hiérarchique) + MemGraphRAG.

Façade stable au-dessus de ``app.*`` : routage hiérarchique, peuplement et retrieval H-MEM,
entités / faits / passages / conflits MemGraphRAG, scoring.
"""
from __future__ import annotations

# H-MEM (routage index-based + scoring)
from app.services.hmem_builder import HMemBuilder  # noqa: F401
from app.services.hmem_retrieval import hmem_retrieve, score_candidate  # noqa: F401
from app.services.hmem_router import HMemRouter  # noqa: F401

# MemGraphRAG (extraction multi-agents, graphe, conflits, gating, PPR conforme)
from app.services.conflict_service import ConflictService, ConflictType  # noqa: F401
from app.services.extraction_agents import (  # noqa: F401
    DetectionAgent, ExtractionAgent, MultiAgentExtractor, ResolutionAgent,
)
from app.services.extraction_service import ExtractionError, ExtractionService  # noqa: F401
from app.services.memgraph_ppr import ppr_retrieve  # noqa: F401
from app.services.memgraph_service import MemGraphService  # noqa: F401
from app.services.schema_gating import SchemaGatingService  # noqa: F401
from app.services.temporal_service import TemporalService  # noqa: F401

__all__ = [
    "HMemBuilder", "hmem_retrieve", "score_candidate", "HMemRouter",
    "ExtractionService", "ExtractionError", "MemGraphService", "TemporalService",
    "ppr_retrieve", "ConflictService", "ConflictType", "SchemaGatingService",
    "ExtractionAgent", "DetectionAgent", "ResolutionAgent", "MultiAgentExtractor",
]
