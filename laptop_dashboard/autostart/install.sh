#!/usr/bin/env bash
# Installe le tableau de bord DENUDATA.IO comme application au démarrage
# de session graphique (GNOME/KDE/XFCE — standard freedesktop XDG autostart).
set -euo pipefail

DASHBOARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$DASHBOARD_DIR/.venv/bin/python"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/denudata-dashboard.desktop"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Environnement virtuel introuvable : $VENV_PYTHON" >&2
  echo "Crée-le d'abord : cd $DASHBOARD_DIR && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p "$AUTOSTART_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=DENUDATA.IO — Tableau de bord matinal
Comment=Agenda de la semaine, tâches Vikunja et idées de nuit au démarrage
Exec=$VENV_PYTHON -m dashboard.main
Path=$DASHBOARD_DIR
X-GNOME-Autostart-enabled=true
Terminal=false
EOF

chmod +x "$DESKTOP_FILE"
echo "Autostart installé : $DESKTOP_FILE"
echo "Le tableau de bord se lancera à la prochaine connexion graphique."
