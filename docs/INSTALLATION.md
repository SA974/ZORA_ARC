# Installation

```bash
cd arc-mem-bridge
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Ne renseignez pas de secret dans `.env.example`. Le fichier `.env` local doit rester privé.

## PostgreSQL

```bash
python scripts/check_postgres.py
python scripts/apply_migrations.py --dry-run
python scripts/apply_migrations.py
```

Les migrations sont idempotentes et créent les extensions avec `if not exists`.

## API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8791
```

Puis tester `GET /health`.
