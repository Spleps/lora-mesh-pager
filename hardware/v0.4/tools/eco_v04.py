"""Разова правка плати v0.4: місце під C29 (режектор 2-ї гармоніки, паралельно L3) і 4 кріпильні отвори M2,5.
Нетлист: route/sch.net. Після — tools/sync_pcb.py і DRC. У gen_pcb.py ті самі елементи вже додано в PLACE."""
import math, os, sys
from pathlib import Path
import pcbnew
sys.path.insert(0, str(Path(__file__).parent)); from netlist import load
FPLIB = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
proj = Path(__file__).resolve().parent.parent
comps, nets = load(proj / "route" / "sch.net")
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb")); mm = pcbnew.FromMM
assert not b.FindFootprintByReference("C29"), "правку вже застосовано"
pin_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
NEW = {"C29": (142.25, 127.6, 90), "H1": (103.5, 103.5, 0), "H2": (140.5, 103.3, 0), "H3": (102.9, 197.1, 0), "H4": (157.1, 197.1, 0)}
for ref, (x, y, rot) in NEW.items():
    c = comps[ref]; lib, name = c["footprint"].split(":")
    fp = pcbnew.FootprintLoad(f"{FPLIB}/{lib}.pretty", name)
    fp.SetReference(ref); fp.SetValue(c["value"]); fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"])); fp.SetSheetfile("lora-pager.kicad_sch"); fp.SetSheetname("/")
    b.Add(fp); fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        n = pin_net.get((ref, pad.GetNumber()))
        if n: pad.SetNet(b.FindNet(n))
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); fp.Reference().SetTextThickness(mm(0.12))
    fp.Value().SetVisible(False)
    if ref == "C29": fp.SetDNP(True)
    if ref.startswith("H"): fp.Reference().SetVisible(False)
# траси C29 <-> L3
def padpos(ref, net):
    return [p for p in b.FindFootprintByReference(ref).Pads() if p.GetNetname() == net][0].GetPosition()
for net in ("/RFO", "/TX1"):
    t = pcbnew.PCB_TRACK(b); t.SetStart(padpos("L3", net)); t.SetEnd(padpos("C29", net)); t.SetWidth(mm(0.35))
    t.SetLayer(pcbnew.F_Cu); t.SetNet(b.FindNet(net)); t.SetLocked(True); b.Add(t)
# зшивальні GND-via під отворами й поруч — прибрати
rm = []
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND":
        px, py = pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)
        if any(r.startswith("H") and math.hypot(px - x, py - y) < 3.3 for r, (x, y, _) in NEW.items()): rm.append(t)
for t in rm: b.Remove(t)
print("added:", list(NEW), "; removed stitching vias:", len(rm))
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(str(proj / "lora-pager.kicad_pcb"))
