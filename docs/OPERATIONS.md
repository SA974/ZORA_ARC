# Operations

Commandes quotidiennes:

```bash
python -m app.cli.arc_mem health
python -m app.cli.arc_mem check-postgres
python -m app.cli.arc_mem apply-migrations --dry-run
python -m app.cli.arc_mem diagnose-hermes
python -m app.cli.arc_mem diagnose-hindsight
python -m app.cli.arc_mem smoke-test
```

Hindsight doit rester en `postgresql_direct` sur cette machine. Les fichiers `.hindsight/config.json`, `.hermes/hindsight/config.json` et `.hindsight/profiles/hermes.env` déclarent PostgreSQL natif et `HINDSIGHT_EMBEDDED_POSTGRES=false`.

Avant toute modification Hermes, créer une sauvegarde timestampée de `~/.hermes/config.yaml` et relire le diff. ARC-MEM Bridge ne modifie pas cette configuration automatiquement.

Pour diagnostiquer PostgreSQL, commencer par `scripts/check_postgres.py`, puis vérifier le service Windows/WSL et le port `5432` si la connexion échoue.
