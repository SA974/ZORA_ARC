# DENUDATA.IO — Tableau de bord matinal

Fenêtre affichée au démarrage du portable : « Bonjour Stéphane », le logo
DENUDATA.IO, l'agenda de la semaine (Vikunja + Google Calendar à venir), la
liste des tâches à réaliser, et un panneau pour ajouter directement dans
Vikunja les idées qui viennent pendant la nuit.

Ce module est **indépendant d'ARC-MEM Bridge** (`app/`, `src/` à la racine du
dépôt) : il ne consomme aucune de ses dépendances et ne doit pas être
configuré sur ce portable pour ARC-MEM — c'est un outil personnel séparé.

## État d'avancement

- [x] Client Vikunja (lecture des tâches, agenda de la semaine, création de
      tâche pour le panneau « Idées de la nuit »)
- [x] Fenêtre native (pywebview) avec la mise en page cible
- [ ] Google Calendar : interface prête (`dashboard/calendar_client.py`),
      câblage OAuth à faire dans une prochaine étape
- [ ] Logo réel : déposer le fichier dans `assets/logo.png` (fallback texte
      tant qu'il est absent)
- [ ] Lancement automatique au démarrage du PC (script fourni, à activer)

## Installation (sur le portable, pas dans cette session distante)

```bash
cd laptop_dashboard
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp .env.example .env
# éditer .env : VIKUNJA_API_TOKEN (jeton généré dans Vikunja > Paramètres > Jetons API)
```

Dépendances système pour pywebview (GTK WebKit) sous Debian/Ubuntu :

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1
```

(Sur d'autres distributions, adapter selon le paquet WebKitGTK disponible.)

## Lancer manuellement

```bash
cd laptop_dashboard
./.venv/bin/python -m dashboard.main
```

## Lancer automatiquement au démarrage du PC

```bash
./autostart/install.sh
```

Installe une entrée XDG autostart (`~/.config/autostart/denudata-dashboard.desktop`)
qui ouvre la fenêtre à chaque connexion à la session graphique.

## Le jeton Vikunja expire

Si le tableau de bord affiche une bannière d'erreur mentionnant un jeton
invalide ou expiré : régénérer un jeton dans Vikunja (Paramètres > Jetons
API), avec si possible une durée d'expiration longue, puis mettre à jour
`VIKUNJA_API_TOKEN` dans `.env`.

## Prochaines étapes prévues

1. Brancher Google Calendar (`dashboard/calendar_client.py`) pour fusionner
   les rendez-vous Google avec l'agenda Vikunja dans la même grille
   hebdomadaire.
2. Déposer le vrai logo DENUDATA.IO dans `assets/logo.png`.
3. Activer et tester l'autostart sur le portable.
