from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    app: dict[str, Any]
    postgres: dict[str, Any]
    hindsight: dict[str, Any]


class RetainRequest(BaseModel):
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecallRequest(BaseModel):
    query: str
    limit: int = 5


class DocumentIngestRequest(BaseModel):
    title: str
    content: str
    source_uri: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    extract: bool = False  # lancer l'extraction MemGraphRAG (entités/relations) par chunk
    detect_conflicts: bool = False


class PdfIngestRequest(BaseModel):
    path: str
    domain: str = "bibliotheque"
    dry_run: bool = False
    max_pages: int = 0


class FolderIngestRequest(BaseModel):
    path: str
    domain: str = "bibliotheque"
    dry_run: bool = False
    max_pages: int = 1500
    max_file_mb: int = 100
    limit: int = 0  # 0 = tous les fichiers
    post_embed_delay: float = 0.0


class ExtractRequest(BaseModel):
    text: str
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    observed_at: str | None = None
    detect_conflicts: bool = False


class SyncHindsightRequest(BaseModel):
    limit: int = 0  # 0 = tous les souvenirs en attente
    min_len: int = 25
    detect_conflicts: bool = False


class FactCreateRequest(BaseModel):
    subject: str
    predicate: str
    object_value: str
    provenance_text: str
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    confidence: float = 0.5
    valid_from: str | None = None
    valid_to: str | None = None
    observed_at: str | None = None


class FeedbackRequest(BaseModel):
    signal: Literal["approval", "neutral", "rebuttal"]
    source: str = "user"
    note: str | None = None


class RetrieveRequest(BaseModel):
    query: str
    expected_evidence_level: Literal["leger", "standard", "renforce", "critique"] = "standard"
    limit: int = 8


class AuditRequest(BaseModel):
    taskcard: dict[str, Any]
    proposed_answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class TaskCard(BaseModel):
    title: str
    objective: str
    central_question: str
    expected_deliverable: str
    provided_data: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    expected_evidence_level: str = "standard"


class ContextBundle(BaseModel):
    memories: list[dict[str, Any]] = Field(default_factory=list)
    route_paths: list[dict[str, Any]] = Field(default_factory=list)
    facts: list[dict[str, Any]] = Field(default_factory=list)
    passages: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
