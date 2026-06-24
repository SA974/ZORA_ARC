# Security

## Secrets

Ne jamais committer `.env`, clés API, tokens ou mots de passe. Les logs utilisent un redactor pour masquer les motifs `nvapi-*`, `sk-*`, tokens, secrets et passwords.

## PostgreSQL local

Le mot de passe PostgreSQL peut être vide si `pg_hba.conf` le permet. ARC-MEM Bridge ne hardcode aucun mot de passe et construit un DSN compatible mot de passe vide.

## Hermes

`~/.hermes/config.yaml` ne doit pas être modifié sans sauvegarde timestampée, diff lisible et validation explicite.

## Hindsight

Hindsight est traité comme mémoire agentique PostgreSQL directe. ARC-MEM Bridge utilise `HINDSIGHT_DATABASE_URL` pour `hindsight_hermes`; cette URL ne doit pas contenir de mot de passe en clair si l’authentification locale n’en requiert pas. Le mode embedded est abandonné sur Windows.
