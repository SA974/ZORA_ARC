from __future__ import annotations

from typing import Any


class PPRService:
    def run_ppr(self, seed_node: str | None = None) -> dict[str, Any]:
        try:
            import networkx as nx
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": "PPR non disponible: networkx absent"}

        from app.db import get_connection

        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("select source_id, target_id, weight from memgraph.v_graphe_ppr limit 5000")
                rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"PPR non disponible: {exc}"}

        graph = nx.DiGraph()
        for row in rows:
            graph.add_edge(str(row["source_id"]), str(row["target_id"]), weight=float(row["weight"]))
        if not graph:
            return {"ok": True, "scores": {}, "warning": "empty graph"}
        personalization = None
        if seed_node and seed_node in graph:
            personalization = {node: 0.0 for node in graph.nodes}
            personalization[seed_node] = 1.0
        scores = nx.pagerank(graph, personalization=personalization, weight="weight")
        ranked = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:20])
        return {"ok": True, "scores": ranked}
