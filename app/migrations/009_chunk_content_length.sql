-- 009_chunk_content_length.sql
-- Définition explicite de la "longueur de contenu" d'un chunk, demandée sans ambiguïté.
--
-- Décision : DEUX champs distincts plutôt qu'un 'content_length' ambigu :
--   content_chars            = nombre de CARACTÈRES Unicode (char_length du texte assaini)
--   content_tokens_estimated = estimation de TOKENS (≈ chars/4, heuristique GPT-like)
--
-- Implémentation : colonnes GÉNÉRÉES VIRTUAL (PostgreSQL 18+) -> calculées à la lecture
-- à partir de `content`. Avantages : autoritaires (aucune dérive vs le texte réel),
-- aucune écriture applicative, idempotentes, justes même sur l'historique, et surtout
-- DDL instantané (changement de métadonnée seul, AUCUNE réécriture de table, pas de
-- verrou long) — décisif sur zora.chunks (~888k lignes).
--
-- NOTE PG18 : on ne peut pas indexer une colonne générée VIRTUAL. Pour auditer la taille,
-- utiliser un index d'expression sur char_length(content) si nécessaire (non créé ici
-- pour rester en DDL instantané ; un build d'index scannerait toute la table).

alter table zora.chunks
  add column if not exists content_chars integer
  generated always as (char_length(content)) virtual;

alter table zora.chunks
  add column if not exists content_tokens_estimated integer
  generated always as (greatest(1, char_length(content) / 4)) virtual;
