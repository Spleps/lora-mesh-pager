#!/bin/bash
# Автотрасування: плата -> DSN -> Freerouting -> SES -> плата (заливки перезаливаються).
# Потрібні: портативна Java 25 у ~/.local/opt/jdk-25*-jre і ~/.local/opt/freerouting/freerouting-2.5.0.jar
set -euo pipefail
PY=${KICAD_PY:-python3}   # на сервері: kicad-python (Flatpak KiCad 10)
cd "$(dirname "$0")/.."
JAVA=$(ls -d ~/.local/opt/jdk-25*-jre | head -1)/bin/java
FR=~/.local/opt/freerouting/freerouting-2.5.0.jar
mkdir -p route
$PY -c "import pcbnew; b=pcbnew.LoadBoard('lora-pager.kicad_pcb'); assert pcbnew.ExportSpecctraDSN(b,'route/lora-pager.dsn')"
"$JAVA" -jar "$FR" -de route/lora-pager.dsn -do route/lora-pager.ses -mp "${PASSES:-40}" ${FR_OPTS:-} --gui.enabled=false
$PY tools/import_ses.py
$PY tools/cleanup.py
$PY tools/stitch.py
