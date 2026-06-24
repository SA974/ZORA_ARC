from app.services.hmem_router import HMEM_LEVELS, HMemRouter


def test_route_query_returns_hierarchy():
    route = HMemRouter().route_query("PostGIS pgvector memory routing")
    levels = [step["level"] for step in route]
    assert levels[:3] == ["domain", "theme", "subtheme"]
    assert set(levels).issubset(set(HMEM_LEVELS))
    assert route[1]["label"] in {"spatial", "postgres_vector", "agentic_memory", "documentary_rag", "general"}
