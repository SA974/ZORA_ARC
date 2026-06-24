# Utiliser ARC-MEM Bridge avec Hermes

Version : ARC-MEM Bridge v0.1  
Architecture cible : ZORA_ARC V9.2 ARC-MEM-H  
Etat courant : Hindsight en `postgresql_direct`, PostgreSQL externe Windows accessible depuis WSL.

## 1. Role d'ARC-MEM Bridge pour Hermes

ARC-MEM Bridge est une couche locale que Hermes peut utiliser pour accéder a plusieurs types de memoire sans les melanger :

- Hindsight : memoire agentique persistante, connectee directement a PostgreSQL dans la base `hindsight_hermes`.
- MemGraphRAG : memoire documentaire probatoire, stockee dans `rag_arc`, schemas `zora` et `memgraph`.
- H-MEM : routeur hierarchique qui aide a choisir les branches de memoire pertinentes.
- ZORA ARC : gouvernance, TASKCARD, niveau de preuve, audit et qualite.

Hermes ne doit pas ecrire directement dans toutes ces couches au hasard. Le role d'ARC-MEM Bridge est de fournir des points d'entree propres.

## 2. Etat actuel a retenir

PostgreSQL :

- Serveur : PostgreSQL 18 Windows.
- Host depuis WSL : `172.21.96.1`.
- Base ARC-MEM : `rag_arc`.
- Base Hindsight directe : `hindsight_hermes`.
- Extensions ARC-MEM actives : `vector`, `postgis`, `pg_trgm`, `pgcrypto`.

Hindsight :

- Mode retenu : `postgresql_direct`.
- Daemon Hindsight : non requis pour cette voie.
- PostgreSQL embedded : abandonne.
- Memoire existante validee : 661 faits, 212 sessions, 14 entites au moment de la mise en place.

Fichiers config deja alignes :

- `.hindsight/config.json`
- `.hermes/hindsight/config.json`
- `.hindsight/profiles/hermes.env`
- `arc-mem-bridge/.env`

## 3. Demarrer ARC-MEM Bridge

Depuis WSL :

```bash
cd /mnt/c/Users/Stephane_Arnoux/arc-mem-bridge
. .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8791
```

L'API locale sera disponible sur :

```text
http://127.0.0.1:8791
```

Verifier :

```bash
python -m app.cli.arc_mem health
```

Resultat attendu :

```json
{
  "postgres": {
    "ok": true,
    "database": "rag_arc"
  },
  "hindsight": {
    "ok": true,
    "mode": "postgresql_direct"
  }
}
```

## 4. Comment Hermes doit appeler ARC-MEM Bridge

Hermes peut utiliser ARC-MEM Bridge de deux manieres :

1. API HTTP locale.
2. Scripts CLI Python.

### Option recommandee : API locale

Utiliser l'API locale quand Hermes doit :

- retenir un souvenir agentique ;
- rappeler du contexte agentique ;
- ingérer un document dans la memoire documentaire ;
- construire un paquet de contexte pour une reponse ;
- auditer une reponse.

### Option alternative : CLI

Utiliser la CLI pour :

- diagnostiquer l'etat ;
- verifier PostgreSQL ;
- appliquer les migrations ;
- faire des tests rapides.

Commandes utiles :

```bash
python -m app.cli.arc_mem health
python -m app.cli.arc_mem check-postgres
python -m app.cli.arc_mem diagnose-hermes
python -m app.cli.arc_mem diagnose-hindsight
python -m app.cli.arc_mem smoke-test
```

## 5. Scenarios d'utilisation depuis Hermes

### Scenario A : Hermes veut retenir une decision utilisateur

Exemple : l'utilisateur decide que Hindsight doit rester en PostgreSQL direct.

Appel API :

```bash
curl -X POST http://127.0.0.1:8791/memory/retain \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Decision: Hindsight doit rester en mode postgresql_direct et ne plus utiliser PostgreSQL embedded.",
    "metadata": {
      "source": "hermes",
      "type": "decision",
      "project": "arc-mem-bridge"
    }
  }'
```

Effet :

- ecrit dans `hindsight_hermes.facts` ;
- ne cree pas de chunk documentaire ;
- ne duplique pas dans MemGraphRAG ;
- reste dans la memoire agentique.

Quand utiliser :

- preferences utilisateur ;
- decisions de projet ;
- conventions de travail ;
- erreurs diagnostiquees ;
- resume intersession ;
- contexte durable Hermes.

Quand ne pas utiliser :

- PDF entier ;
- corpus documentaire lourd ;
- chunks RAG ;
- preuves scientifiques longues.

### Scenario B : Hermes veut rappeler du contexte agentique

Appel API :

```bash
curl -X POST http://127.0.0.1:8791/memory/recall \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hindsight postgresql_direct",
    "limit": 5
  }'
```

Effet :

- recherche dans `hindsight_hermes.facts` ;
- retourne des souvenirs agentiques ;
- permet a Hermes de recuperer les decisions et le contexte deja connus.

Utilisation typique par Hermes :

```text
Avant de repondre sur ARC-MEM Bridge, appelle /memory/recall avec la question utilisateur.
Utilise les souvenirs comme contexte, mais ne les presente pas comme preuves documentaires.
```

### Scenario C : Hermes veut ingérer un document probatoire

Appel API :

```bash
curl -X POST http://127.0.0.1:8791/ingest/document \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Note technique MemGraphRAG",
    "content": "MemGraphRAG conserve les passages, les faits, les relations et les preuves.",
    "source_uri": "local://notes/memgraphrag",
    "metadata": {
      "source_type": "note",
      "domain": "architecture"
    }
  }'
```

Effet :

- cree un document dans `zora.documents` ;
- cree des chunks dans `zora.chunks` ;
- prepare la future extraction MemGraphRAG ;
- conserve une provenance documentaire.

Quand utiliser :

- notes techniques ;
- extraits de PDF ;
- documents scientifiques ;
- specifications ;
- rapports ;
- passages a citer.

Quand ne pas utiliser :

- preference personnelle courte ;
- decision d'organisation ;
- memoire intersession Hermes.

### Scenario D : Hermes veut construire un contexte avant de repondre

Appel API :

```bash
curl -X POST http://127.0.0.1:8791/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explique la separation entre Hindsight, MemGraphRAG et H-MEM",
    "expected_evidence_level": "standard",
    "limit": 8
  }'
```

Effet :

ARC-MEM Bridge retourne un `ContextBundle` avec :

- `taskcard` : cadrage ZORA ARC ;
- `zora_router` : score et modules actifs ;
- `memories` : contexte Hindsight ;
- `route_paths` : chemin H-MEM ;
- `facts` : faits MemGraphRAG ;
- `passages` : chunks documentaires ;
- `citations` : provenance ;
- `warnings` : limites.

Important :

`/retrieve` ne produit pas une reponse finale longue. Il produit le paquet de contexte que Hermes doit utiliser pour rediger ensuite.

Workflow recommande pour Hermes :

1. Recevoir la question utilisateur.
2. Appeler `/retrieve`.
3. Lire `taskcard`, `memories`, `facts`, `passages`, `citations`.
4. Rediger une reponse courte ou longue selon la demande.
5. Ne citer comme preuve que les elements provenant de `facts`, `passages` ou `citations`.
6. Utiliser `memories` comme contexte agentique, pas comme preuve documentaire.

### Scenario E : Hermes veut auditer une reponse

Appel API :

```bash
curl -X POST http://127.0.0.1:8791/audit \
  -H "Content-Type: application/json" \
  -d '{
    "taskcard": {
      "title": "Verifier une reponse ARC-MEM"
    },
    "proposed_answer": "Hindsight est la memoire documentaire principale.",
    "sources": [],
    "citations": [],
    "limits": [],
    "risks": []
  }'
```

Effet :

Retourne des `findings` si la reponse manque :

- sources ;
- citations ;
- limites ;
- risques.

Utilisation recommandee :

Avant une reponse importante, Hermes peut appeler `/audit` pour verifier que la reponse respecte le niveau de preuve attendu.

## 6. Regles de decision pour Hermes

### Utiliser Hindsight quand la demande concerne :

- "Qu'avons-nous decide ?"
- "Rappelle-toi ma preference."
- "Quelle configuration ai-je validee ?"
- "Que s'est-il passe dans la derniere session ?"
- "Quels problemes avons-nous deja diagnostiques ?"

Endpoint recommande :

```text
/memory/recall
```

ou via :

```text
/retrieve
```

### Utiliser MemGraphRAG quand la demande concerne :

- preuves ;
- citations ;
- passages documentaires ;
- faits extraits de documents ;
- comparaison de sources ;
- conflits entre documents.

Endpoint recommande :

```text
/ingest/document
/retrieve
```

### Utiliser H-MEM quand la demande est large ou floue

H-MEM intervient automatiquement dans `/retrieve`. Hermes n'a pas besoin de l'appeler directement.

Exemples :

- "Explique l'architecture generale."
- "Retrouve les elements sur PostgreSQL, Hindsight et MemGraphRAG."
- "Va du concept general aux preuves detaillees."

### Utiliser ZORA ARC quand il faut cadrer ou auditer

ZORA ARC intervient automatiquement dans `/retrieve` et `/audit`.

Il sert a :

- qualifier la tache ;
- fixer un niveau de preuve ;
- activer les modules utiles ;
- detecter les manques de sources, limites et risques.

## 7. Prompt type pour Hermes

Tu peux utiliser ce texte comme instruction durable dans Hermes ou comme convention de travail :

```text
Quand une question concerne ARC-MEM, Hindsight, MemGraphRAG, PostgreSQL,
H-MEM ou ZORA ARC :

1. Appelle ARC-MEM Bridge sur http://127.0.0.1:8791.
2. Pour le contexte agentique, utilise /memory/recall ou /retrieve.
3. Pour retenir une decision ou preference durable, utilise /memory/retain.
4. Pour les documents et preuves, utilise /ingest/document puis /retrieve.
5. Ne confonds jamais Hindsight et MemGraphRAG :
   - Hindsight = memoire agentique.
   - MemGraphRAG = memoire documentaire probatoire.
6. Traite les souvenirs Hindsight comme contexte, pas comme preuve documentaire.
7. Pour une reponse importante, appelle /audit avant finalisation.
8. Ne jamais exposer de cle API, token, mot de passe ou contenu .env.
```

## 8. Exemple de flux complet

Objectif : Hermes doit repondre a une question technique sur l'architecture.

### Etape 1 : rappeler le contexte agentique

```bash
curl -X POST http://127.0.0.1:8791/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "architecture ARC-MEM Hindsight MemGraphRAG", "limit": 5}'
```

### Etape 2 : construire le contexte complet

```bash
curl -X POST http://127.0.0.1:8791/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "architecture ARC-MEM Hindsight MemGraphRAG H-MEM",
    "expected_evidence_level": "renforce",
    "limit": 10
  }'
```

### Etape 3 : rediger

Hermes utilise :

- les souvenirs Hindsight pour comprendre les decisions passees ;
- les passages et citations pour les preuves ;
- le routeur H-MEM pour organiser la reponse ;
- la TASKCARD pour rester dans le cadre.

### Etape 4 : auditer

```bash
curl -X POST http://127.0.0.1:8791/audit \
  -H "Content-Type: application/json" \
  -d '{
    "taskcard": {"title": "Architecture ARC-MEM"},
    "proposed_answer": "...",
    "sources": [{"source": "ContextBundle"}],
    "citations": [{"chunk_id": "example"}],
    "limits": ["Prototype v0.1"],
    "risks": ["Extraction LLM documentaire encore a finaliser"]
  }'
```

## 9. Diagnostics si Hermes ne voit pas ARC-MEM

### Verifier que l'API tourne

```bash
curl http://127.0.0.1:8791/health
```

### Verifier la CLI

```bash
python -m app.cli.arc_mem health
```

### Verifier PostgreSQL

```bash
python scripts/check_postgres.py
```

### Verifier Hindsight direct

```bash
python scripts/diagnose_hindsight.py
```

### Verifier Hermes

```bash
python scripts/diagnose_hermes.py
```

## 10. Problemes frequents

### PostgreSQL refuse la connexion depuis WSL

Verifier que `.env` contient :

```text
POSTGRES_HOST=172.21.96.1
POSTGRES_PORT=5432
```

Verifier aussi que `pg_hba.conf` autorise le subnet WSL.

### Hindsight tente encore de demarrer embedded

Verifier :

```text
.hindsight/config.json
.hermes/hindsight/config.json
.hindsight/profiles/hermes.env
```

Les valeurs attendues :

```text
mode = postgresql_direct
embedded_postgres = false
HINDSIGHT_EMBEDDED_POSTGRES=false
```

### Hermes confond souvenir et preuve

Rappel :

- Hindsight donne du contexte agentique.
- MemGraphRAG donne les preuves documentaires.
- Les citations doivent venir de `zora`, `memgraph`, `passages`, `chunks`, pas uniquement de Hindsight.

### L'API repond mais sans resultats documentaires

Cela signifie probablement que les documents n'ont pas encore ete ingeres dans `zora.documents` et `zora.chunks`, ou que l'extraction MemGraphRAG n'a pas encore ete executee.

## 11. Bonnes pratiques

- Toujours demarrer par `/health`.
- Utiliser `/memory/retain` uniquement pour la memoire agentique.
- Utiliser `/ingest/document` pour les contenus probatoires.
- Utiliser `/retrieve` avant une reponse complexe.
- Utiliser `/audit` avant une reponse critique.
- Ne jamais mettre de secret dans un prompt Hermes.
- Ne jamais demander a Hermes de modifier `.hermes/config.yaml` sans sauvegarde.
- Ne jamais reactiver PostgreSQL embedded pour Hindsight sur cette machine.

## 12. Resume operationnel

Pour Hermes, ARC-MEM Bridge est le point d'entree local :

```text
Hermes -> ARC-MEM Bridge -> PostgreSQL
                         -> Hindsight postgresql_direct
                         -> MemGraphRAG
                         -> H-MEM
                         -> ZORA ARC
```

La regle principale :

```text
Hindsight se souvient du travail.
MemGraphRAG prouve avec des documents.
H-MEM route.
ZORA ARC gouverne.
PostgreSQL centralise.
Hermes orchestre via ARC-MEM Bridge.
```
