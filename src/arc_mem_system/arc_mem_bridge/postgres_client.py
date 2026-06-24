"""Client PostgreSQL (façade -> app.db)."""
from app.db import (  # noqa: F401
    DatabaseHealth,
    check_database_health,
    check_extensions,
    get_connection,
    test_connection,
)
