"""Імпорт трас із route/lora-pager.ses у плату, перезаливка полігонів, збереження."""
from pathlib import Path
import pcbnew
proj = Path(__file__).resolve().parent.parent
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb"))
assert pcbnew.ImportSpecctraSES(b, str(proj / "route" / "lora-pager.ses")), "SES не імпортовано"
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(proj / "lora-pager.kicad_pcb"))
print("tracks:", len(b.GetTracks()))
