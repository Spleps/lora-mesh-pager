"""GND-переходи по сітці: з'єднують острівці верхньої/нижньої заливки з суцільною GND на In1.
Ставить via тільки там, де до чужих цепей, отворів, краю й keepout антени ESP32 достатньо місця."""
import math
from pathlib import Path
import pcbnew

STEP, VIA_D, VIA_DRILL, GAP = 2.5, 0.6, 0.3, 0.35   # мм
proj = Path(__file__).resolve().parent.parent
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb"))
mm, to = pcbnew.FromMM, pcbnew.ToMM
gnd = b.FindNet("GND")
edge = b.GetBoardEdgesBoundingBox()
x0, y0, x1, y1 = to(edge.GetX()), to(edge.GetY()), to(edge.GetRight()), to(edge.GetBottom())

obst = []   # (тип, геометрія, запас)
for fp in b.GetFootprints():
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        same = pad.GetNetname() == "GND"
        obst.append(("box", (to(bb.GetX()), to(bb.GetY()), to(bb.GetRight()), to(bb.GetBottom())), 0.0, 0.15 if same else GAP))
    for z in fp.Zones():          # keepout антени
        bb = z.GetBoundingBox()
        obst.append(("box", (to(bb.GetX()), to(bb.GetY()), to(bb.GetRight()), to(bb.GetBottom())), 0.3, 0.0))
    if fp.GetReference() in ("J1", "J3", "J4", "SW1", "J2", "J5", "U1"):   # під роз'ємами й модулем — без via
        bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else fp.GetBoundingBox()
        obst.append(("box", (to(bb.GetX()), to(bb.GetY()), to(bb.GetRight()), to(bb.GetBottom())), 0.0, 0.0))
for t in b.GetTracks():
    w = to(t.GetWidth()) / 2
    same = t.GetNetname() == "GND"
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition(); obst.append(("pt", (to(p.x), to(p.y)), w, 0.3 if same else GAP))
    else:
        a, c = t.GetStart(), t.GetEnd(); obst.append(("seg", (to(a.x), to(a.y), to(c.x), to(c.y)), w, 0.1 if same else GAP))

def dist_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)

def free(px, py, cap=None, d=VIA_D):
    """cap — максимальний запас (для острівців 0,22 мм замість 0,35)."""
    r = d / 2
    if px - r < x0 + 1 or py - r < y0 + 1 or px + r > x1 - 1 or py + r > y1 - 1: return False
    for kind, g, half, gap in obst:
        m = half + (min(gap, cap) if cap is not None else gap)
        if kind == "box":
            if g[0] - r - m < px < g[2] + r + m and g[1] - r - m < py < g[3] + r + m: return False
        elif kind == "pt":
            if math.hypot(px - g[0], py - g[1]) < r + m: return False
        elif dist_seg(px, py, *g) < r + m: return False
    return True

def free_track(px, py, own_pad):
    """Точка траси 0,25 мм: не ближче 0,2 мм до чужих площадок і трас."""
    r = 0.125 + 0.2
    for kind, g, half, gap in obst:
        m = half + gap
        if kind == "box":
            if g[0] - r < px < g[2] + r and g[1] - r < py < g[3] + r:
                bb = own_pad.GetBoundingBox()
                if not (to(bb.GetX()) - 0.01 <= g[0] + 0.15 + 0.01 and abs(g[2] - 0.15 - to(bb.GetRight())) < 0.02): return False
        elif kind == "seg" and m > 0.2 and dist_seg(px, py, *g) < r + (m - GAP):
            return False
    return True

n = 0
y = y0 + 1.5
while y < y1 - 1:
    x = x0 + 1.5
    while x < x1 - 1:
        if free(x, y):
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(gnd); b.Add(v)
            obst.append(("pt", (x, y), 0.3, 0.3)); n += 1
        x += STEP
    y += STEP
pcbnew.ZONE_FILLER(b).Fill(b.Zones())

# Другий прохід: острівці верхньої/нижньої заливки, у яких немає жодного GND-via, отримують власний via.
def gnd_points():
    pts = [t.GetPosition() for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    pts += [p.GetPosition() for f in b.GetFootprints() for p in f.Pads()
            if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    return pts
extra = 0
for z in b.Zones():
    if z.GetZoneName() not in ("GND_top", "GND_bottom"): continue
    poly = z.GetFilledPolysList(z.GetLayer())
    for i in range(poly.OutlineCount()):
        ol = poly.Outline(i)
        if any(ol.PointInside(v) for v in gnd_points()): continue
        bb = ol.BBox(); done = False
        yy = to(bb.GetY()) + 0.2
        while yy < to(bb.GetBottom()) and not done:
            xx = to(bb.GetX()) + 0.2
            while xx < to(bb.GetRight()) and not done:
                pt = pcbnew.VECTOR2I(mm(xx), mm(yy))
                if ol.PointInside(pt) and free(xx, yy, cap=0.22, d=0.45):
                    v = pcbnew.PCB_VIA(b); v.SetPosition(pt); v.SetWidth(mm(0.45)); v.SetDrill(mm(0.2))
                    v.SetNet(gnd); b.Add(v); obst.append(("pt", (xx, yy), 0.225, 0.3)); extra += 1; done = True
                xx += 0.1
            yy += 0.1
        if not done:   # вузький острівець: via поруч із GND-площадкою + коротка траса до неї
            gp = [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == "GND" and ol.PointInside(p.GetPosition())]
            for pd in gp:
                px, py = to(pd.GetPosition().x), to(pd.GetPosition().y)
                for r in [0.9 + 0.1 * k for k in range(15)]:
                    for ang in range(0, 360, 15):
                        vx, vy = px + r * math.cos(math.radians(ang)), py + r * math.sin(math.radians(ang))
                        path_ok = all(free_track(px + (vx - px) * u, py + (vy - py) * u, pd) for u in [i / 10 for i in range(3, 11)])
                        if free(vx, vy, cap=0.22, d=0.45) and path_ok:
                            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy))); v.SetWidth(mm(0.45)); v.SetDrill(mm(0.2))
                            v.SetNet(gnd); b.Add(v)
                            t = pcbnew.PCB_TRACK(b); t.SetStart(pd.GetPosition()); t.SetEnd(v.GetPosition()); t.SetWidth(mm(0.25))
                            t.SetLayer(z.GetLayer()); t.SetNet(gnd); b.Add(t)
                            obst.append(("pt", (vx, vy), 0.225, 0.3)); extra += 1; done = True; break
                    if done: break
                if done: break
        if not done:
            print(f"увага: острівець без via біля x={to(bb.GetX()):.1f} y={to(bb.GetY()):.1f}")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(str(proj / "lora-pager.kicad_pcb"))
print("stitching vias:", n, "+ island vias:", extra)
