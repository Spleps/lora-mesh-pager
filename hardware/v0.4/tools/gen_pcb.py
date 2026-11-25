"""Збирання друкованої плати LoRa-пейджера з нетлиста схеми (pcbnew API, KiCad 10).

4 шари: F.Cu сигнали, In1.Cu GND, In2.Cu сигнали й +3V3, B.Cu сигнали.
Плата 60 x 100 мм. Посадкові місця прив'язані до символів схеми (Update PCB from Schematic працює).
Траси цей скрипт не малює: після нього експорт DSN -> Freerouting -> імпорт SES.

Запуск із папки проєкту:
  kicad-cli sch export netlist --format kicadsexpr -o /tmp/pager.net lora-pager.kicad_sch
  python3 tools/gen_pcb.py /tmp/pager.net
"""
import json, sys
from pathlib import Path
import pcbnew

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
sys.path.insert(0, str(HERE))
import netlist  # noqa: E402

import os
FPLIB = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
OX, OY = 100.0, 100.0          # лівий верхній кут плати в координатах KiCad
W, H = 60.0, 100.0
mm = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))

# ---------- розміщення: ref -> (x, y, поворот°) у мм від лівого верхнього кута ----------
PLACE = {
    # 4. Радіо + 5. RF (правий верхній кут, антена SMA на верхньому краї)
    "J5": (50.0, 2.6, 90),
    "C28": (53.2, 5.4, 0), "L8": (50.0, 6.6, 90), "C27": (53.2, 8.6, 0), "C26": (50.0, 10.4, 90),
    "U6": (47.0, 14.5, 0),
    "R16": (42.5, 11.0, 0), "C22": (42.5, 9.0, 0), "R15": (53.5, 14.5, 90), "C21": (56.0, 14.5, 90),   # R15/C21 — біля вив. 4 (CTRL), R16/C22 — біля вив. 6 (VDD)
    "C20": (40.5, 14.0, 90), "C19": (37.6, 16.2, 0), "L5": (40.5, 18.0, 90), "C18": (37.6, 20.0, 0),
    "L4": (40.5, 22.0, 90), "C17": (37.6, 24.0, 0), "L3": (40.5, 26.0, 90), "C29": (42.25, 26.0, 90), "L2": (37.6, 28.4, 0),
    "C23": (47.4, 18.6, 90), "L6": (45.6, 23.2, 270), "C24": (48.6, 23.2, 270),
    "L7": (44.0, 26.4, 90), "C25": (50.6, 26.4, 90),
    "U2": (46.5, 31.5, 0),
    "C13": (41.2, 31.2, 270), "C14": (39.3, 31.2, 270),
    "Y1": (40.0, 36.0, 0), "C15": (37.0, 35.0, 90), "R14": (40.5, 39.8, 0), "C16": (43.6, 39.8, 0),
    "C10": (47.6, 38.4, 0), "C11": (47.6, 36.4, 0), "L1": (49.2, 42.2, 0), "C12": (44.4, 36.8, 90),
    # 3. Дисплей: модуль OLED над платою на гребінці J3 (контур на шовкографії)
    "H1": (3.5, 3.5, 0), "H2": (40.5, 3.3, 0), "H3": (2.9, 97.1, 0), "H4": (57.1, 97.1, 0),   # кріпильні отвори M2,5
    "J3": (12.2, 4.0, 90), "R12": (31.0, 4.0, 0), "R13": (31.0, 6.4, 0),
    # Кнопки інтерфейсу
    "SW4": (7.0, 38.0, 0), "SW5": (18.0, 38.0, 0), "SW6": (29.0, 38.0, 0),
    # 1. Живлення (лівий край: USB-C, вимикач)
    "J1": (4.0, 55.0, 270), "U5": (12.5, 55.0, 0), "R1": (11.5, 50.0, 0), "R2": (11.5, 60.5, 0),
    "D1": (19.0, 47.0, 0), "Q1": (19.0, 52.5, 0), "R5": (19.0, 57.5, 0),
    "U3": (26.5, 47.5, 0), "R3": (31.0, 47.5, 90), "C1": (26.5, 51.5, 0), "C2": (26.5, 54.0, 0),
    "R4": (31.0, 51.5, 0), "D2": (31.0, 54.0, 0),
    "SW1": (4.5, 68.0, 270), "R6": (11.0, 68.0, 90),
    "U4": (17.0, 66.0, 0), "C3": (17.0, 62.0, 0), "C4": (22.5, 65.0, 90), "C5": (24.5, 65.0, 90),
    "J2": (52.5, 58.0, 90), "R7": (45.0, 52.0, 0), "R8": (45.0, 54.5, 0), "C6": (45.0, 57.0, 0),
    # 2. MCU внизу, антена Wi-Fi на нижньому краї
    "U1": (30.0, 87.25, 180),
    "C7": (15.0, 75.0, 0), "C8": (15.0, 77.5, 0), "R9": (15.0, 81.0, 0), "C9": (15.0, 83.5, 0),
    "SW2": (7.0, 79.0, 90), "SW3": (7.0, 89.0, 90), "R10": (15.0, 87.0, 0),
    "R11": (45.0, 76.0, 0), "D3": (45.0, 78.5, 0), "J4": (55.0, 72.0, 0),
}
REF_POS = {"C29": (42.7, 25.55, 0), "L7": (45.5, 28.0, 90)}   # абсолютні координати написів (мм від кута плати)
RADIO_SHIFT = ['C29', 'C28', 'L8', 'C27', 'C26', 'U6', 'R15', 'C21', 'R16', 'C22', 'C20', 'C19', 'L5', 'C18', 'L4', 'C17', 'L3', 'L2', 'C23', 'L6', 'C24', 'L7', 'C25', 'U2', 'C13', 'C14', 'Y1', 'C15', 'R14', 'C16', 'C10', 'C11', 'L1', 'C12']
RF_NETS = ["RFO", "TX1", "TX2", "TX3", "SW_RF1", "SW_RF2", "SW_RFC", "RX_IN", "RFI_P", "RFI_N", "ANT_M1", "ANT", "SX_VR_PA"]
POWER_NETS = ["GND", "+3V3", "VBUS", "VSYS", "VBAT"]


def write_project():
    """Правила й класи кіл у .kicad_pro (KiCad бере їх під час відкриття плати)."""
    pro = PROJ / "lora-pager.kicad_pro"
    d = json.loads(pro.read_text()) if pro.exists() else {}
    def cls(name, tw, cl, vd, vh, prio):
        return {"name": name, "track_width": tw, "clearance": cl, "via_diameter": vd, "via_drill": vh,
                "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "bus_width": 12,
                "wire_width": 6, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": prio}
    d["net_settings"] = {
        "classes": [cls("Default", 0.2, 0.2, 0.45, 0.2, 2147483647), cls("Power", 0.4, 0.2, 0.7, 0.35, 0),
                    cls("RF", 0.35, 0.2, 0.45, 0.2, 1)],
        "meta": {"version": 4}, "net_colors": None, "netclass_assignments": None,
        # локальні мітки схеми отримують префікс "/" (наприклад /ANT), символи живлення — ні
        "netclass_patterns": [{"netclass": "Power", "pattern": n if n[0] in "+G" or n == "VBUS" else "/" + n} for n in POWER_NETS] +
                             [{"netclass": "RF", "pattern": "/" + n} for n in RF_NETS]}
    d.setdefault("meta", {"filename": "lora-pager.kicad_pro", "version": 3})
    pro.write_text(json.dumps(d, indent=2, ensure_ascii=False))


def zone(board, net, layer, pts, prio=0, name=""):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNet(board.FindNet(net)); z.SetAssignedPriority(prio)
    z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)  # оторвані острівці заливки прибирати
    z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.3))
    if name: z.SetZoneName(name)
    o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(mm(OX + x), mm(OY + y))
    board.Add(z)


# ---------- ручна розводка виводів SX1262 (QFN, крок 0,5 мм): закріплені траси, решту веде Freerouting ----------
def fanout_u2(board):
    U = board.FindFootprintByReference("U2")
    pad = {p.GetNumber(): p for p in U.Pads()}
    def xy(n):
        q = pad[n].GetPosition(); return (pcbnew.ToMM(q.x) - OX, pcbnew.ToMM(q.y) - OY)
    def padxy(ref, net):
        f = board.FindFootprintByReference(ref)
        q = [p for p in f.Pads() if p.GetNetname() == net][0].GetPosition()
        return (pcbnew.ToMM(q.x) - OX, pcbnew.ToMM(q.y) - OY)
    def trk(net, pts, w):
        for a, c in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(mm(w))
            t.SetLayer(pcbnew.F_Cu); t.SetNet(board.FindNet(net)); t.SetLocked(True); board.Add(t)
    def via(net, x, y, d=0.45, h=0.2):
        v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetWidth(mm(d)); v.SetDrill(mm(h))
        v.SetNet(board.FindNet(net)); v.SetLocked(True); board.Add(v)
    # SPI/IRQ праворуч: два ряди via зі зсувом, щоб пройти між ними
    for n, net, col in [("13", "/LORA_DIO1", 0), ("15", "/LORA_NRST", 0), ("17", "/LORA_MOSI", 0),
                        ("14", "/LORA_BUSY", 1), ("16", "/LORA_MISO", 1), ("18", "/LORA_SCK", 1)]:
        x, y = xy(n); vx = x + 1.16 + col * 1.0
        trk(net, [(x, y), (vx, y)], 0.12); via(net, vx, y)
    # NSS угору-праворуч на via
    x, y = xy("19"); trk("/LORA_NSS", [(x, y), (x, y - 1.06), (x + 0.9, y - 1.06)], 0.15); via("/LORA_NSS", x + 0.9, y - 1.06)
    # RFO: до L3 і дроселя L2
    x, y = xy("23"); yh = y - 0.86; l3 = padxy("L3", "/RFO"); l2 = padxy("L2", "/RFO")
    trk("/RFO", [(x, y), (x, yh)], 0.25); trk("/RFO", [(x, yh), (l3[0], yh), l3], 0.35); trk("/RFO", [(l3[0], yh), (l2[0], yh), l2], 0.35)
    # C29 (режектор 2-ї гармоніки) паралельно L3
    trk("/RFO", [l3, padxy("C29", "/RFO")], 0.35); trk("/TX1", [padxy("L3", "/TX1"), padxy("C29", "/TX1")], 0.35)
    # VR_PA: ліворуч під RFO до L2, C13, C14
    x, y = xy("24"); l2v = padxy("L2", "/SX_VR_PA")
    trk("/SX_VR_PA", [(x, y), (x - 0.6, y)], 0.25); trk("/SX_VR_PA", [(x - 0.6, y), (l2v[0], y), l2v], 0.35)
    for r in ("C13", "C14"):
        c = padxy(r, "/SX_VR_PA"); trk("/SX_VR_PA", [(c[0], y), c], 0.35)
    # RFI_N угору до L6, відгалуження на L7
    x, y = xy("22"); l6 = padxy("L6", "/RFI_N"); l7 = padxy("L7", "/RFI_N"); yk = l7[1]
    trk("/RFI_N", [(x, y), (x, y - 1.71)], 0.2); trk("/RFI_N", [(x, y - 1.71), (l6[0], yk)], 0.25); trk("/RFI_N", [(l6[0], yk), l6], 0.35); trk("/RFI_N", [(l6[0], yk), l7], 0.35)
    # RFI_P угору-праворуч до C24 і C25
    x, y = xy("21"); c24 = padxy("C24", "/RFI_P"); c25 = padxy("C25", "/RFI_P"); yk = c25[1]
    trk("/RFI_P", [(x, y), (x, y - 1.56)], 0.2); trk("/RFI_P", [(x, y - 1.56), (x + 0.82, yk)], 0.25); trk("/RFI_P", [(x + 0.82, yk), c25], 0.35); trk("/RFI_P", [(c24[0], yk), c24], 0.35)
    # тепловідвідні via в центральній площадці
    cx, cy = xy("25")
    for dx in (-0.6, 0.6):
        for dy in (-0.6, 0.6): via("GND", cx + dx, cy + dy)


def main(netpath):
    comps, nets = netlist.load(netpath)
    write_project()
    board = pcbnew.NewBoard(str(PROJ / "lora-pager.kicad_pcb"))
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.m_MinThroughDrill = mm(0.2)
    ds.m_ViasMinSize = mm(0.45)
    ds.m_TrackMinWidth = mm(0.1)            # Freerouting звужує трасу біля виводів QFN; JLC 4 шари: 0,09 мм
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)   # In1 — суцільна GND, трасувальник по ній не веде
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_SIGNAL)  # In2 — третій сигнальний шар (+3V3 трасами)          # термопереходы под ESP32 (0,2 мм; JLC 4 шари дозволяє)
    ds.m_CopperEdgeClearance = 0              # реальний мінімум 0,3 мм задає правило в .kicad_dru
    board.SetLayerName(pcbnew.In1_Cu, "In1.Cu")
    tb = board.GetTitleBlock()
    tb.SetTitle("LoRa mesh-пейджер: ESP32-S3 + SX1262, 433 МГц"); tb.SetRevision("0.1"); tb.SetDate("2026-11-09")
    tb.SetCompany("НУ «Львівська політехніка», ЕЛ-12")
    tb.SetComment(0, "4 шари, 1,6 мм, JLC04161H-7628: In1 = GND (опора для RF), In2 = сигнали та +3V3")

    nmap = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); nmap[name] = ni
    pin_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

    for r in RADIO_SHIFT:  # відступ від корпусу SMA (його courtyard до y=5,6)
        x, y, a = PLACE[r]; PLACE[r] = (x, y + 1.6, a)
    missing = [r for r in comps if r not in PLACE]
    assert not missing, f"немає координат: {missing}"
    for ref, c in sorted(comps.items()):
        lib, name = c["footprint"].split(":")
        fp = pcbnew.FootprintLoad(f"{FPLIB}/{lib}.pretty", name)
        fp.SetReference(ref); fp.SetValue(c["value"])
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        if c["uuid"]:
            fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"]))
        fp.SetSheetfile("lora-pager.kicad_sch"); fp.SetSheetname("/")
        x, y, rot = PLACE[ref]
        board.Add(fp)
        fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            n = pin_net.get((ref, pad.GetNumber()))
            if n: pad.SetNet(nmap[n])
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); fp.Reference().SetTextThickness(mm(0.12))
        fp.Value().SetVisible(False)
        if ref.startswith("H"): fp.Reference().SetVisible(False)
        if ref in REF_POS:                       # написи, які інакше лягають на сусідні площадки
            rx, ry, ra = REF_POS[ref]; fp.Reference().SetPosition(P(rx, ry)); fp.Reference().SetTextAngleDegrees(ra)
        for k, v in c.get("fields", {}).items():
            if k not in ("Footprint", "Datasheet", "Description") and v:
                fp.SetField(k, v)
                fld = fp.GetField(k)
                if fld: fld.SetVisible(False)
        if c["value"].startswith("TBD") or ref in ("R12", "R13", "C25", "L7", "C27", "C28", "C29"):
            fp.SetDNP(ref in ("R12", "R13", "C25", "L7", "C27", "C28", "C29"))

    fanout_u2(board)

    # контур плати із заокругленими кутами
    r = 2.0
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetWidth(mm(0.1)); board.Add(s)
    def arc(c, start, mid, end):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetArcGeometry(P(*start), P(*mid), P(*end)); s.SetWidth(mm(0.1)); board.Add(s)
    k = r * (1 - 2 ** -0.5)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc(None, (W - r, 0), (W - k, k), (W, r)); arc(None, (W, H - r), (W - k, H - k), (W - r, H))
    arc(None, (r, H), (k, H - k), (0, H - r)); arc(None, (0, r), (k, k), (r, 0))

    # контур модуля OLED 0,96'' (27,3 x 27,8 мм) на шовкографії
    for a, b in [((1.5, 1.5), (28.8, 1.5)), ((28.8, 1.5), (28.8, 29.3)), ((28.8, 29.3), (1.5, 29.3)), ((1.5, 29.3), (1.5, 1.5))]:
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.F_SilkS)
        s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetWidth(mm(0.15)); board.Add(s)
    for txt, (x, y), sz in [("OLED 0.96 SSD1306", (15.0, 16.0), 1.0),
                            ("LoRa pager v0.4  ESP32-S3 + SX1262 433 MHz", (30.0, 72.0), 1.0),
                            ("+", (48.5, 58.0), 1.2), ("-", (48.5, 56.0), 1.2), ("BAT", (48.2, 60.9), 0.8)]:   # полярність J2
        t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(pcbnew.F_SilkS); t.SetPosition(P(x, y))
        t.SetTextSize(pcbnew.VECTOR2I(mm(sz), mm(sz))); t.SetTextThickness(mm(0.15)); board.Add(t)

    # площини: In1 = GND; In2 = +3V3, під RF/радіо = GND; зовнішні шари — GND-заливка
    full = [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]
    rf = [(33.5, 0.3), (W - 0.3, 0.3), (W - 0.3, 46.0), (33.5, 46.0)]
    zone(board, "GND", pcbnew.In1_Cu, full, 0, "GND_plane")
    zone(board, "GND", pcbnew.F_Cu, full, 0, "GND_top")
    zone(board, "GND", pcbnew.B_Cu, full, 0, "GND_bottom")

    board.Save(str(PROJ / "lora-pager.kicad_pcb"))
    (PROJ / "lora-pager.kicad_dru").write_text('''(version 1)
# SMA J5 монтується на торець плати: її контакти за конструкцією доходять до краю.
(rule "board edge"
  (condition "!(A.memberOfFootprint('J5') || B.memberOfFootprint('J5'))")
  (constraint edge_clearance (min 0.3mm)))
''', encoding="utf-8")
    print("ok:", len(comps), "footprints,", len(nets), "nets")


if __name__ == "__main__":
    main(sys.argv[1])
