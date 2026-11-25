"""Прибирає «хвости» автотрасувальника: тільки те, що сам DRC KiCad позначив як via_dangling / track_dangling.
Елементи шукаються за UUID із JSON-звіту DRC; повторює, доки хвостів не залишиться (максимум 6 разів).
Плата завантажується ОДИН раз (повторний LoadBoard у Flatpak-збірці інколи повертає не BOARD)."""
import json, os, subprocess, tempfile
from pathlib import Path
import pcbnew

proj = Path(__file__).resolve().parent.parent
pcb = proj / "lora-pager.kicad_pcb"
tmp = proj / "route"; tmp.mkdir(exist_ok=True)     # /tmp у Flatpak ізольований — звіт пишемо в проєкт
b = pcbnew.LoadBoard(str(pcb))
total = 0
for _ in range(6):
    rpt = tmp / "cleanup-drc.json"
    subprocess.run([os.environ.get("KICAD_CLI", "kicad-cli"), "pcb", "drc", "--format", "json", "--severity-all", "-o", str(rpt), str(pcb)],
                   check=True, capture_output=True)
    data = json.loads(rpt.read_text())
    ids = {it["uuid"] for v in data.get("violations", []) if v.get("type") in ("via_dangling", "track_dangling")
           for it in v.get("items", [])}
    victims = [t for t in list(b.GetTracks()) if t.m_Uuid.AsString() in ids] if ids else []
    if not victims:
        break
    for t in victims:
        b.Remove(t)
    total += len(victims)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(str(pcb))
print("removed dangling items:", total)
