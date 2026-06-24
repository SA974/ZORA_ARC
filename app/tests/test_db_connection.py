from app.db import check_database_health


def test_db_health_shape():
    health = check_database_health().as_dict()
    assert "ok" in health
    assert "extensions" in health
    assert set(["vector", "postgis", "pg_trgm", "pgcrypto"]).issubset(health["extensions"].keys())
