"""Разова правка плати (v0.3): у PE4259 були переплутані виводи 4 (CTRL) і 6 (VDD).
Щоб не перетинати траси біля ключа, R15/C21 і R16/C22 міняються місцями: локальні траси біля U6 лишаються,
перейменовуються лише їхні кола. Знімаються траса /SX_DIO2 і відгалуження +3V3 до старого R16 — їх дотрасує Freerouting
(tools/finish_route.sh). Нетлист: route/sch.net."""
import sys
from pathlib import Path
import pcbnew
sys.path.insert(0, str(Path(__file__).parent)); from netlist import load
proj = Path(__file__).resolve().parent.parent
comps, nets = load(proj / "route" / "sch.net")
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb"))
F = b.FindFootprintByReference
assert F("U6").FindPadByNumber("4").GetNetname() == "Net-(U6-VDD)", "правку вже застосовано?"
# 1) поміняти місцями
for a, c in (("R15", "R16"), ("C21", "C22")):
    fa, fc = F(a), F(c)
    pa, oa, pc, oc = fa.GetPosition(), fa.GetOrientation(), fc.GetPosition(), fc.GetOrientation()
    fa.SetPosition(pc); fa.SetOrientation(oc); fc.SetPosition(pa); fc.SetOrientation(oa)
# 2) локальні траси: поміняти кола
nv, ncn = b.FindNet("Net-(U6-VDD)"), b.FindNet("Net-(U6-CTRL)")
for t in list(b.GetTracks()):
    if t.GetNetname() == "Net-(U6-VDD)": t.SetNet(ncn)
    elif t.GetNetname() == "Net-(U6-CTRL)": t.SetNet(nv)
# 3) кола площадок, значення і прив'язка до символів — з нетлиста
pin2net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
for fp in b.GetFootprints():
    ref = fp.GetReference(); c = comps[ref]
    fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"])); fp.SetValue(c["value"])
    for pad in fp.Pads():
        n = pin2net.get((ref, pad.GetNumber()))
        if n and pad.GetNetname() != n:
            ni = b.FindNet(n); assert ni, n
            print("pad", ref, pad.GetNumber(), pad.GetNetname(), "->", n); pad.SetNet(ni)
# 4) зняти /SX_DIO2 і відгалуження +3V3 до колишнього R16.1
rm = [t for t in b.GetTracks() if t.GetNetname() == "/SX_DIO2"]
cur = F("R15").FindPadByNumber("1").GetPosition()          # тепер тут R15.1 (колишній R16.1)
near = lambda a, c: abs(a.x - c.x) <= 2000 and abs(a.y - c.y) <= 2000
segs = [t for t in b.GetTracks() if t.GetNetname() == "+3V3" and t.Type() != pcbnew.PCB_VIA_T]
used = set()
while True:
    nx = [t for t in segs if id(t) not in used and (near(t.GetStart(), cur) or near(t.GetEnd(), cur))]
    if len(nx) != 1: break
    t = nx[0]; used.add(id(t)); rm.append(t); cur = t.GetEnd() if near(t.GetStart(), cur) else t.GetStart()
for t in rm: b.Remove(t)
print("removed tracks/vias:", len(rm))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(proj / "lora-pager.kicad_pcb"))
