"""Знімає зшивальні GND-via (не підключені до жодної траси), щоб дотрасувати плату."""
from pathlib import Path
import pcbnew
proj = Path(__file__).resolve().parent.parent
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb"))
ends = set()
for t in b.GetTracks():
    if t.GetClass() != "PCB_VIA":
        ends.add((t.GetStart().x, t.GetStart().y)); ends.add((t.GetEnd().x, t.GetEnd().y))
pads = [p for fp in b.GetFootprints() for p in fp.Pads()]
rm = []
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        pos = t.GetPosition()
        if (pos.x, pos.y) not in ends and not any(p.HitTest(pos) for p in pads):
            rm.append(t)
for v in rm: b.Remove(v)
b.Save(str(proj / "lora-pager.kicad_pcb"))
print("removed stitching vias:", len(rm))
