"""Правка плати v0.5, без повного перетрасування:
 1) C7/C8 перенесено впритул до виводу 3V3 модуля ESP32 (були за ~65 мм по трасі);
 2) шар In2 - полігон +3V3 (широке живлення замість тонкої траси), нові перехідні біля LDO, ESP32 і FB1;
 3) окрема гілка живлення радіо /3V3_RF через феритову намистину FB1;
 4) SW_RF1 (ФНЧ -> RF-ключ) переведено на верхній шар без via;
 5) ширші траси VBUS/VBAT і вузла DC-DC на нижньому шарі; напис версії.
Перед запуском: tools/unstitch.py. Після: tools/sync_pcb.py, tools/cleanup.py, tools/stitch.py, DRC. Нетлист: route/sch.net."""
import math, os, sys
from pathlib import Path
import pcbnew
sys.path.insert(0, str(Path(__file__).parent)); from netlist import load
FPLIB = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
proj = Path(__file__).resolve().parent.parent
comps, nets = load(proj / "route" / "sch.net")
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb")); mm, to = pcbnew.FromMM, pcbnew.ToMM
FP = {f.GetReference(): f for f in b.GetFootprints()}      # кеш: після змін FindFootprintByReference у SWIG ламається
assert "FB1" not in FP, "правку вже застосовано"
F = lambda r: FP[r]
PAD = {(f.GetReference(), p.GetNumber()): p for f in FP.values() for p in f.Pads()}
OX = OY = 100.0
def V(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))
def xy(v): return (to(v.x) - OX, to(v.y) - OY)
def padxy(ref, num): return xy(PAD[(ref, num)].GetPosition())
def trk(net, pts, w, layer=pcbnew.F_Cu):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(V(*a)); t.SetEnd(V(*c)); t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)
def via(net, x, y, d=0.7, h=0.35):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(mm(d)); v.SetDrill(mm(h)); v.SetNet(b.FindNet(net)); b.Add(v)
DEAD = []          # видалення - наприкінці: після BOARD.Remove() обгортки SWIG повертають нетипізовані об'єкти
def kill(t): DEAD.append(t)
def tracks(net): return [t for t in b.GetTracks() if t.GetNetname() == net and not any(t is d or t.m_Uuid == d.m_Uuid for d in DEAD)]
def near(p, q, tol=0.12): return math.hypot(p[0]-q[0], p[1]-q[1]) < tol
def is_via(t): return t.Type() == pcbnew.PCB_VIA_T

b.Add(pcbnew.NETINFO_ITEM(b, "/3V3_RF"))

# ---- FB1 ----
c = comps["FB1"]; lib, name = c["footprint"].split(":")
fb = pcbnew.FootprintLoad(f"{FPLIB}/{lib}.pretty", name)
fb.SetReference("FB1"); fb.SetValue(c["value"]); fb.SetFPID(pcbnew.LIB_ID(lib, name))
fb.SetPath(pcbnew.KIID_PATH("/" + c["uuid"])); fb.SetSheetfile("lora-pager.kicad_sch"); fb.SetSheetname("/")
b.Add(fb); FP["FB1"] = fb
for p in fb.Pads(): PAD[("FB1", p.GetNumber())] = p
fb.SetPosition(V(53.8, 47.0)); fb.SetOrientationDegrees(90)
if padxy("FB1", "1")[1] < 47.0: fb.SetOrientationDegrees(270)      # вивід 1 (+3V3) - знизу, з боку живлення
fb.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); fb.Reference().SetTextThickness(mm(0.12)); fb.Value().SetVisible(False)
fb.Reference().SetPosition(V(55.9, 47.0))

# ---- C7/C8 до виводу 2 модуля ----
p2 = padxy("U1", "2")
diag = [t for t in tracks("+3V3") if not is_via(t) and to(t.GetLength()) > 14 and (near(xy(t.GetStart()), (42.4, 90.8), 0.3) or near(xy(t.GetEnd()), (42.4, 90.8), 0.3))]
assert len(diag) == 1, len(diag)
E = xy(diag[0].GetStart()) if near(xy(diag[0].GetStart()), (42.4, 90.8), 0.3) else xy(diag[0].GetEnd())
for t in tracks("+3V3"):          # старий відвід від виводу 2
    if not is_via(t) and t.GetLayer() == pcbnew.F_Cu and to(t.GetLength()) < 3 and 38.5 < xy(t.GetStart())[0] < 42.6 and 90.5 < xy(t.GetStart())[1] < 91.5:
        kill(t)
def put(ref, x, y, rot, want1):
    f = F(ref); f.SetPosition(V(x, y)); f.SetOrientationDegrees(rot)
    if not near(padxy(ref, "1"), want1, 0.3): f.SetOrientationDegrees(rot + 180)
    assert near(padxy(ref, "1"), want1, 0.3), (ref, padxy(ref, "1"))
d8 = abs(padxy("C8", "1")[0] - padxy("C8", "2")[0] + padxy("C8", "1")[1] - padxy("C8", "2")[1]) / 2
put("C8", 42.0, E[1] - d8, 90, (42.0, E[1]))
put("C7", 42.1, 92.55, 0, (41.15, 92.55))
c71 = padxy("C7", "1"); k = p2[1] - E[1]
trk("+3V3", [p2, (40.0, p2[1]), (40.0 + k, E[1]), E], 0.5)
trk("+3V3", [(c71[0], E[1]), c71], 0.5)
via("+3V3", E[0] + 0.8, E[1] - 0.8); via("+3V3", E[0] + 2.0, E[1] - 2.0)
via("GND", 42.0, E[1] - 2 * d8 - 1.25, 0.6, 0.3); via("GND", 44.55, 92.55, 0.6, 0.3)

# ---- перехідні +3V3 біля LDO ----
c5 = padxy("C5", "1")
trk("+3V3", [c5, (26.3, c5[1]), (27.7, c5[1])], 0.5); via("+3V3", 26.3, c5[1]); via("+3V3", 27.7, c5[1])

# ---- SW_RF1 на верхній шар ----
for t in tracks("/SW_RF1"): kill(t)
a = [xy(p.GetPosition()) for p in F("C20").Pads() if p.GetNetname() == "/SW_RF1"][0]; u = padxy("U6", "1")
dy = u[1] - a[1]
trk("/SW_RF1", [a, (u[0] - 0.9 - abs(dy), a[1]), (u[0] - 0.9, u[1]), u], 0.35)

# ---- гілка радіо: зняти старий підвід In2, розрізати трасу під FB1 ----
for t in tracks("+3V3"):
    if is_via(t) or t.GetLayer() != pcbnew.In2_Cu: continue
    s, e = xy(t.GetStart()), xy(t.GetEnd())
    for q1, q2 in (((30.0, 18.8), (43.1, 31.9)), ((30.0, 5.3), (30.0, 18.8))):
        if (near(s, q1, 0.2) and near(e, q2, 0.2)) or (near(s, q2, 0.2) and near(e, q1, 0.2)): kill(t)
f1, f2 = padxy("FB1", "1"), padxy("FB1", "2")
cut = [t for t in tracks("+3V3") if not is_via(t) and t.GetLayer() == pcbnew.F_Cu and abs(xy(t.GetStart())[0] - 53.8) < 0.15 and abs(xy(t.GetEnd())[0] - 53.8) < 0.15
       and min(xy(t.GetStart())[1], xy(t.GetEnd())[1]) < 46 < 48 < max(xy(t.GetStart())[1], xy(t.GetEnd())[1])]
assert len(cut) == 1, len(cut)
s, e = sorted([xy(cut[0].GetStart()), xy(cut[0].GetEnd())], key=lambda q: q[1]); kill(cut[0])
trk("+3V3", [e, (f1[0], 49.6), f1], 0.4); via("+3V3", f1[0], 49.6)
trk("+3V3", [f2, s], 0.4)

# ---- кола площадок з нетлиста ----
pin_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}
for fp in FP.values():
    for pad in fp.Pads():
        n = pin_net.get((fp.GetReference(), pad.GetNumber()))
        if n and pad.GetNetname() != n: pad.SetNet(b.FindNet(n))

# ---- траси, з'єднані з виводами /3V3_RF, переходять у цю цеп ----
def dseg(p, a, c):
    vx, vy = c[0]-a[0], c[1]-a[1]; L2 = vx*vx + vy*vy
    k = 0 if L2 == 0 else max(0, min(1, ((p[0]-a[0])*vx + (p[1]-a[1])*vy) / L2))
    return math.hypot(p[0]-a[0]-k*vx, p[1]-a[1]-k*vy)
items = tracks("+3V3")
def touch(i, j):
    vi, vj = is_via(i), is_via(j)
    if not vi and not vj and i.GetLayer() != j.GetLayer(): return False
    pi = [xy(i.GetPosition())] if vi else [xy(i.GetStart()), xy(i.GetEnd())]
    pj = [xy(j.GetPosition())] if vj else [xy(j.GetStart()), xy(j.GetEnd())]
    if vi and vj: return False
    if vi: return dseg(pi[0], *pj) < 0.1
    if vj: return dseg(pj[0], *pi) < 0.1
    return any(dseg(p, *pj) < 0.06 for p in pi) or any(dseg(p, *pi) < 0.06 for p in pj)
seeds = [PAD[(r, n)] for r, n in nets["/3V3_RF"]]
front = [t for t in items if any((pad.HitTest(t.GetPosition()) if is_via(t) else (t.GetLayer() == pcbnew.F_Cu and (pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd())))) for pad in seeds)]
done = set(id(t) for t in front); group = list(front)
while front:
    cur = front.pop()
    for t in items:
        if id(t) not in done and touch(cur, t): done.add(id(t)); group.append(t); front.append(t)
rf = b.FindNet("/3V3_RF")
xs = [xy(t.GetPosition())[0] for t in group]; ys = [xy(t.GetPosition())[1] for t in group]
for t in group: t.SetNet(rf)
print(f"/3V3_RF: {len(group)} трас/via, x {min(xs):.1f}..{max(xs):.1f}, y {min(ys):.1f}..{max(ys):.1f}")

# ---- ширини ----
for t in b.GetTracks():
    if is_via(t) or any(t.m_Uuid == d.m_Uuid for d in DEAD): continue
    n, L, w = t.GetNetname(), t.GetLayer(), to(t.GetWidth())
    if n in ("VBUS", "/VBAT") and L == pcbnew.In2_Cu and w < 0.59: t.SetWidth(mm(0.6))
    if n in ("VBUS", "/VBAT") and L == pcbnew.F_Cu and w < 0.39: t.SetWidth(mm(0.4))
    if n == "Net-(U2-DCC_SW)" and L == pcbnew.B_Cu: t.SetWidth(mm(0.4))

# ---- полігон +3V3 на In2 (крім зони радіо) ----
z = pcbnew.ZONE(b); z.SetLayer(pcbnew.In2_Cu); z.SetNet(b.FindNet("+3V3")); z.SetAssignedPriority(0)
z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); z.SetZoneName("3V3 plane")
o = z.Outline(); o.NewOutline()
for x, y in ((0.3, 0.3), (34.0, 0.3), (34.0, 46.0), (59.7, 46.0), (59.7, 99.7), (0.3, 99.7)): o.Append(mm(OX + x), mm(OY + y))
b.Add(z)

for dr in b.GetDrawings():
    if hasattr(dr, "GetText") and "v0.4" in dr.GetText(): dr.SetText(dr.GetText().replace("v0.4", "v0.5"))
for t in DEAD: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(proj / "lora-pager.kicad_pcb"))
print("ok")
