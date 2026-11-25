"""Генератор принципової схеми LoRa mesh-пейджера (ESP32-S3 + SX1262, 433 МГц) для KiCad.

Стиль «як малюють вручну»: обв'язка стоїть біля виводів мікросхем і з'єднана проводами;
мітки кіл — лише для зв'язків між блоками (SPI, I2C, USB, RF). Запуск: python3 gen_sch.py <папка_проєкту>
"""
import math, re, sys, uuid
from pathlib import Path

import os
LIBDIR = Path(os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols"))
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
NAME = "lora-pager"
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, "lora-pager-root"))
_n = 0
def uid():
    global _n; _n += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"lora-pager-{_n}"))

# ---------- бібліотеки символів ----------
def block(text, name):
    i = text.find(f'(symbol "{name}"')
    if i < 0: raise KeyError(name)
    d = 0
    for j in range(i, len(text)):
        if text[j] == "(": d += 1
        elif text[j] == ")":
            d -= 1
            if d == 0: return text[i:j + 1]

# Нумерація виводів звірена з даташитом pSemi PE4259 (DOC-03694, табл. 7): 1 RF1, 2 GND, 3 RF2, 4 CTRL, 5 RFC, 6 VDD (або /CTRL).
# У v0.1–v0.2 виводи 4 і 6 були переплутані (CTRL сидів на 6, VDD на 4) — з такою розводкою ключ ніколи не вмикав RX.
PE4259 = '''(symbol "PE4259"
  (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
  (property "Reference" "U" (at 0 8.89 0) (effects (font (size 1.27 1.27))))
  (property "Value" "PE4259" (at 0 -8.89 0) (effects (font (size 1.27 1.27))))
  (property "Footprint" "Package_TO_SOT_SMD:SOT-363_SC-70-6" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (property "Datasheet" "https://www.psemi.com/pdf/datasheets/pe4259ds.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (property "Description" "SPDT RF switch DC-3 GHz, SC-70-6 (pSemi/Murata)" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (symbol "PE4259_0_1" (rectangle (start -7.62 6.35) (end 7.62 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
  (symbol "PE4259_1_1"
    (pin passive line (at -10.16 2.54 0) (length 2.54) (name "RF1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
    (pin power_in line (at 0 -8.89 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
    (pin passive line (at -10.16 -2.54 0) (length 2.54) (name "RF2" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
    (pin power_in line (at 0 8.89 270) (length 2.54) (name "VDD" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
    (pin passive line (at 10.16 0 180) (length 2.54) (name "RFC" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
    (pin input line (at 10.16 -2.54 180) (length 2.54) (name "CTRL" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
  )
  (embedded_fonts no)
)'''

_cache, LIBSYMS = {}, {}
def libsym(lib_id):
    """Повернути (текст для lib_symbols, список виводів) з розгортанням extends."""
    if lib_id in _cache: return _cache[lib_id]
    lib, name = lib_id.split(":")
    if lib == "pager":
        b = PE4259; parent, child = name, name
    else:
        t = (LIBDIR / f"{lib}.kicad_sym").read_text(encoding="utf-8")
        b = block(t, name); child = name
        m = re.search(r'\(extends "([^"]+)"\)', b)
        if m:
            parent = m.group(1); pb = block(t, parent)
            for prop in ("Value", "Footprint", "Datasheet", "Description", "ki_keywords", "ki_fp_filters"):
                cm = re.search(rf'\(property "{prop}" "((?:[^"\\]|\\.)*)"', b)
                if cm:
                    pb = re.sub(rf'(\(property "{prop}" )"(?:[^"\\]|\\.)*"', lambda mm: mm.group(1) + '"' + cm.group(1) + '"', pb, count=1)
            b = pb.replace(f'"{parent}_', f'"{child}_')
            b = b.replace(f'(symbol "{parent}"', f'(symbol "{child}"', 1)
        else:
            parent = name
    full = b.replace(f'(symbol "{child}"', f'(symbol "{lib_id}"', 1)
    pins = []
    for m in re.finditer(r'\(pin (\w+) \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)(.*?)\(number "([^"]*)"', full, re.S):
        pins.append(dict(type=m.group(1), x=float(m.group(2)), y=float(m.group(3)), a=int(m.group(4)), num=m.group(6)))
    _cache[lib_id] = (full, pins); LIBSYMS[lib_id] = full
    return _cache[lib_id]

# ---------- геометрія ----------
G = 1.27
def snap(v): return round(round(v / G) * G, 4)
def fmt(v): return f"{v:.4f}".rstrip("0").rstrip(".")
STEP = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}      # екранні y донизу

def pin_pos(sx, sy, rot, p, mirror=None):
    x, y, a = p["x"], p["y"], p["a"]
    if mirror == "x": y, a = -y, (360 - a) % 360
    if mirror == "y": x, a = -x, (180 - a) % 360
    t = math.radians(rot)
    px = x * math.cos(t) - y * math.sin(t)
    py = x * math.sin(t) + y * math.cos(t)
    return snap(sx + px), snap(sy - py), (a + rot + 180) % 360

WIRES, LABELS, TEXTS, NCS, symbols = [], [], [], [], []
PINS, PINPTS, BOM = {}, [], []
POWER = {"GND": "power:GND", "+3V3": "power:+3V3", "VBUS": "power:VBUS"}
PWR_ROT = {"power:GND": {270: 0, 90: 180, 0: 90, 180: 270}}
PWR_ROT["power:+3V3"] = PWR_ROT["power:VBUS"] = {90: 0, 270: 180, 0: 270, 180: 90}
_cnt = {"#PWR": 0, "#FLG": 0}

def tw(s, size=1.27): return len(s) * size * 0.85          # оцінка ширини тексту

def sym_instance(lib_id, ref, value, fp, x, y, rot, pins, mirror=None, dnp=False, extra=None,
                 rpos=None, vpos=None, just=None, hide_ref=False):
    rx, ry = rpos or (x, y); vx, vy = vpos or (x, y)
    fa = 0 if rot == 180 else rot              # кут поля = поворот (крім 180) -> текст горизонтальний і не догори дриґом
    j = f" (justify {just})" if just else ""
    mir = f" (mirror {mirror})" if mirror else ""
    pwr = ref.startswith("#")
    s = [f'(symbol (lib_id "{lib_id}") (at {fmt(x)} {fmt(y)} {rot}){mir} (unit 1) (exclude_from_sim no) (in_bom {"no" if pwr or ref.startswith("H") else "yes"}) (on_board {"no" if pwr else "yes"}) (dnp {"yes" if dnp else "no"}) (uuid "{uid()}")',
         f'  (property "Reference" "{ref}" (at {fmt(rx)} {fmt(ry)} {fa}) (effects (font (size 1.27 1.27)){j}{" (hide yes)" if hide_ref else ""}))',
         f'  (property "Value" "{value}" (at {fmt(vx)} {fmt(vy)} {fa}) (effects (font (size 1.27 1.27)){j}{" (hide yes)" if lib_id == "power:PWR_FLAG" else ""}))',
         f'  (property "Footprint" "{fp}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
         f'  (property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
    for k, v in (extra or {}).items():
        s.append(f'  (property "{k}" "{v}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
    for n in sorted({p["num"] for p in pins}):
        s.append(f'  (pin "{n}" (uuid "{uid()}"))')
    s.append(f'  (instances (project "{NAME}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
    s.append(")")
    symbols.append("\n".join(s))

def place(ref, lib_id, value, fp, x, y, rot=0, mirror=None, dnp=False, note=None, rpos=None, vpos=None, just=None):
    """Поставити символ; повернути {номер_виводу: (x, y, напрямок_назовні)}."""
    x, y = snap(x), snap(y)
    _, pins = libsym(lib_id)
    pp = {p["num"]: pin_pos(x, y, rot, p, mirror) for p in pins}
    if len(pins) == 2 and not ref.startswith("#") and rpos is None:
        if rot in (90, 270):                   # горизонтальний: написи над і під
            rpos, vpos = (x, y - 2.54), (x, y + 2.54)
        else:                                  # вертикальний: написи праворуч
            rpos = (x + 1.9 + tw(ref) / 2, y - 1.27); vpos = (x + 1.9 + tw(value) / 2, y + 1.27)
    sym_instance(lib_id, ref, value, fp, x, y, rot, pins, mirror, dnp, {"Note": note} if note else None,
                 rpos, vpos, just, hide_ref=ref.startswith("#"))
    PINS[ref] = pp
    for num, (px, py, _) in pp.items():
        PINPTS.append((px, py, ref, num))
    if not ref.startswith(("#", "H")):
        BOM.append((ref, value, fp, note or ""))
    return pp

def P(ref, num): return PINS[ref][num][:2]

def W(*pts):
    pts = [(snap(a), snap(b)) for a, b in pts]
    for a, b in zip(pts, pts[1:]):
        assert a[0] == b[0] or a[1] == b[1], ("не ортогонально", a, b)
        if a != b: WIRES.append((a, b))

def go(pt, d, L=2.54):
    dx, dy = STEP[d]; return (snap(pt[0] + dx * L), snap(pt[1] + dy * L))

def psym(net, pt, d):
    """Символ живлення виводом у точку pt, малюнок у бік d."""
    lid = POWER[net]; _, pp = libsym(lid); _cnt["#PWR"] += 1
    place(f"#PWR{_cnt['#PWR']:03d}", lid, net, "", pt[0], pt[1], PWR_ROT[lid][d])

def pwr(pt, net, d=None, L=2.54):
    """Короткий провід від точки й символ живлення на кінці (за замовчуванням GND донизу, живлення догори)."""
    d = d if d is not None else (270 if net == "GND" else 90)
    e = go(pt, d, L); W(pt, e); psym(net, e, d)

def flag(pt):
    _cnt["#FLG"] += 1
    place(f"#FLG{_cnt['#FLG']:02d}", "power:PWR_FLAG", "PWR_FLAG", "", pt[0], pt[1])

def lab(net, pt, d=0, size=1.27):
    """Мітка кола в точці проводу; d — куди йде текст."""
    LABELS.append((net, snap(pt[0]), snap(pt[1]), d, size))

def stub(ref, num, net, L=2.54):
    """Вивід -> короткий провід -> мітка (зв'язок з іншим блоком)."""
    x, y, d = PINS[ref][num]; e = go((x, y), d, L); W((x, y), e); lab(net, e, d)

# 2-вивідні: V — вертикально (вивід 1 угорі, flip — унизу), H — горизонтально (1 ліворуч, flip — праворуч)
def V(ref, lib, val, fp, x, ytop, flip=False, **k):
    return place(ref, lib, val, fp, x, ytop + 3.81, 180 if flip else 0, **k)
def H(ref, lib, val, fp, xl, y, flip=False, **k):
    return place(ref, lib, val, fp, xl + 3.81, y, 270 if flip else 90, **k)
R0603, C0603, C0805, L0603 = ("Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric",
                              "Capacitor_SMD:C_0805_2012Metric", "Inductor_SMD:L_0603_1608Metric")
def RV(ref, val, x, yt, flip=False, **k): return V(ref, "Device:R", val, R0603, x, yt, flip, **k)
def CV(ref, val, x, yt, flip=False, fp=C0603, **k): return V(ref, "Device:C", val, fp, x, yt, flip, **k)
def LV(ref, val, x, yt, flip=False, fp=L0603, **k): return V(ref, "Device:L", val, fp, x, yt, flip, **k)
def RH(ref, val, xl, y, flip=False, **k): return H(ref, "Device:R", val, R0603, xl, y, flip, **k)
def CH(ref, val, xl, y, flip=False, fp=C0603, **k): return H(ref, "Device:C", val, fp, xl, y, flip, **k)
def LH(ref, val, xl, y, flip=False, fp=L0603, **k): return H(ref, "Device:L", val, fp, xl, y, flip, **k)

def text(s, x, y, size=1.27, bold=False):
    s = s.replace('"', "'")
    TEXTS.append(f'(text "{s}" (exclude_from_sim no) (at {fmt(x)} {fmt(y)} 0) (effects (font (size {size} {size}){" (bold yes)" if bold else ""}) (justify left top)) (uuid "{uid()}"))')
def box(x1, y1, x2, y2, title):
    TEXTS.append(f'(rectangle (start {fmt(x1)} {fmt(y1)}) (end {fmt(x2)} {fmt(y2)}) (stroke (width 0.2) (type dash)) (fill (type none)) (uuid "{uid()}"))')
    text(title, x1 + 2, y1 + 2, 1.8, True)

# =====================================================================
# 1. ЖИВЛЕННЯ
# =====================================================================
box(10, 15, 168, 148, "1. ЖИВЛЕННЯ: USB-C, заряд Li-ion, USB/батарея, LDO 3,3 В")
# --- USB-C, CC-резистори, ESD ---
J1 = place("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
           27.94, 50.8, rpos=(27.94, 29.21), vpos=(27.94, 26.67))
W(P("J1", "A4"), (50.8, 35.56)); pwr((50.8, 35.56), "VBUS"); flag((46.99, 35.56))
W(P("J1", "A5"), (63.5, 40.64)); RV("R1", "5.1k", 63.5, 40.64); pwr(P("R1", "2"), "GND")
W(P("J1", "B5"), (53.34, 43.18)); RV("R2", "5.1k", 53.34, 43.18); pwr(P("R2", "2"), "GND")
W(P("J1", "A7"), (48.26, 48.26)); W(P("J1", "B7"), (48.26, 50.8))
W(P("J1", "A6"), (45.72, 53.34)); W(P("J1", "B6"), (45.72, 55.88))
W(P("J1", "SH"), (20.32, 76.2), (33.02, 76.2)); W(P("J1", "A1"), (27.94, 76.2)); pwr((27.94, 76.2), "GND")
flag((33.02, 76.2))
place("U5", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", 66.04, 81.28, rot=180,
      rpos=(73.66, 73.66), vpos=(80.01, 86.36))
W((48.26, 48.26), (48.26, 78.74), P("U5", "4")); lab("USB_DN", (50.8, 78.74))
W((45.72, 53.34), (45.72, 81.28), P("U5", "6")); lab("USB_DP", (50.8, 81.28))
pwr(P("U5", "2"), "GND", 90); pwr(P("U5", "5"), "VBUS", 270)
stub("U5", "3", "USB_DN"); stub("U5", "1", "USB_DP")
text("ESD: D+/D- проходять крізь U5 до ESP32", 48.26, 94.0, 1.0)
text("R1, R2 5,1к на CC: USB-C пристрій-споживач", 12.7, 86.36, 1.0)

# --- зарядка MCP73831 ---
place("U3", "Battery_Management:MCP73831-2-OT", "MCP73831-2-OT", "Package_TO_SOT_SMD:SOT-23-5", 35.56, 119.38,
      rpos=(39.37, 110.49), vpos=(35.56, 134.62))
W(P("U3", "4"), (35.56, 104.14)); psym("VBUS", (35.56, 104.14), 90)
W((35.56, 106.68), (22.86, 106.68)); CV("C1", "4.7u", 22.86, 106.68, fp=C0805); pwr(P("C1", "2"), "GND")
W(P("U3", "5"), (17.78, 121.92)); RV("R3", "2k", 17.78, 121.92, note="Iзар = 1000/R = 500 мА"); pwr(P("R3", "2"), "GND")
pwr(P("U3", "2"), "GND")
place("D2", "Device:LED", "RED", "LED_SMD:LED_0603_1608Metric", 60.96, 121.92, rpos=(60.96, 118.75), vpos=(60.96, 125.1))
W(P("U3", "1"), P("D2", "1"))
RH("R4", "1k", 77.47, 121.92, flip=True)
W(P("D2", "2"), P("R4", "2")); W(P("R4", "1"), (88.9, 121.92), (88.9, 119.38)); psym("VBUS", (88.9, 119.38), 90)
W(P("U3", "3"), (48.26, 116.84), (48.26, 106.68), (63.5, 106.68)); lab("VBAT", (55.88, 106.68))
CV("C2", "4.7u", 50.8, 106.68, fp=C0805); pwr(P("C2", "2"), "GND")
place("J2", "Connector_Generic:Conn_01x02", "BATT Li-ion 1S", "Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal",
      68.58, 106.68, rpos=(70.6, 104.14), vpos=(70.6, 111.76), just="left")
W(P("J2", "2"), (60.96, 109.22)); pwr((60.96, 109.22), "GND")
text("D2 світить під час заряду", 50.8, 127.0, 1.0)
text("J2: вив.1 = +, вив.2 = GND - звірити з дротом акумулятора!", 50.8, 130.0, 1.0)
text("Акумулятор - лише із вбудованою платою захисту (PCM).", 50.8, 132.6, 1.0)
text("R3: Iзар = 1000/R3 = 500 мА", 12.7, 137.16, 1.0)

# --- USB/батарея: D1 + Q1 ---
text("Q1: є USB -> Q1 закритий, живлення через D1;", 86.36, 22.86, 1.0)
text("немає USB -> R5 відкриває Q1, живлення від батареї", 86.36, 25.4, 1.0)
text("U6: вив.4 CTRL <- DIO2 (1 = TX: RFC-RF1; 0 = RX: RFC-RF2), вив.6 VDD = 3,3 В", 165.1, 252.73, 1.1)
place("D1", "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", 104.14, 35.56, rot=180,
      rpos=(104.14, 32.39), vpos=(104.14, 38.74))
pwr((93.98, 35.56), "VBUS"); W((93.98, 35.56), P("D1", "2"))
place("Q1", "Transistor_FET:AO3401A", "AO3401A", "Package_TO_SOT_SMD:SOT-23", 116.84, 50.8, mirror="x",
      rpos=(122.0, 49.53), vpos=(122.0, 52.07), just="left")
W((96.52, 35.56), (96.52, 50.8), P("Q1", "1"))
RV("R5", "10k", 104.14, 50.8, note="стягує затвор Q1; 10k, щоб зворотний струм витоку D1 не тримав Q1 закритим"); pwr(P("R5", "2"), "GND")
W(P("D1", "1"), (119.38, 35.56), (134.62, 35.56)); W(P("Q1", "2"), (119.38, 35.56))
lab("VSYS", (127.0, 35.56)); flag((124.46, 35.56))
W(P("Q1", "3"), (119.38, 60.96)); lab("VBAT", (119.38, 60.96), 270)

# --- вимикач + LDO ---
place("U4", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5", 142.24, 83.82,
      rpos=(142.24, 76.2), vpos=(142.24, 97.79))
W((134.62, 35.56), P("U4", "1"))
W((134.62, 60.96), (142.24, 60.96)); CV("C3", "1u", 142.24, 60.96); pwr(P("C3", "2"), "GND")
place("SW1", "Switch:SW_SPDT", "POWER", "Button_Switch_SMD:SW_SPDT_PCM12", 111.76, 83.82, mirror="y",
      rpos=(111.76, 78.74), vpos=(111.76, 90.17))
W((134.62, 68.58), (101.6, 68.58), (101.6, 81.28), P("SW1", "1"))
W(P("SW1", "3"), (104.14, 86.36)); pwr((104.14, 86.36), "GND")
W(P("SW1", "2"), P("U4", "3")); RV("R6", "100k", 124.46, 83.82); pwr(P("R6", "2"), "GND")
pwr(P("U4", "2"), "GND")
W(P("U4", "5"), (160.02, 81.28)); pwr((160.02, 81.28), "+3V3")
CV("C4", "10u", 152.4, 81.28, fp=C0805); pwr(P("C4", "2"), "GND")
CV("C5", "100n", 160.02, 81.28); pwr(P("C5", "2"), "GND")
text("SW1 вмикає LDO (EN), R6 тримає EN=0", 99.06, 101.6, 1.0)

# --- дільник батареї ---
W((106.68, 107.95), (106.68, 110.49)); lab("VBAT", (106.68, 107.95), 90)
RV("R7", "100k", 106.68, 110.49); RV("R8", "100k", 106.68, 118.11); pwr(P("R8", "2"), "GND")
W(P("R7", "2"), (124.46, 118.11)); CV("C6", "100n", 116.84, 118.11); pwr(P("C6", "2"), "GND")
lab("BAT_ADC", (124.46, 118.11))
text("Дільник 1:2 -> ADC (IO1 ESP32)", 99.06, 134.62, 1.0)

# =====================================================================
# 2. MCU
# =====================================================================
box(172, 15, 290, 148, "2. MCU: ESP32-S3-WROOM-1 (N16R8)")
place("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N16R8", "RF_Module:ESP32-S3-WROOM-1", 233.68, 78.74,
      rpos=(240.03, 106.68), vpos=(236.22, 112.4), just="left")
# живлення + розв'язка прямо біля виводу 3V3
W(P("U1", "2"), (233.68, 40.64), (248.92, 40.64)); pwr((233.68, 40.64), "+3V3")
CV("C7", "10u", 241.3, 40.64, fp=C0805); pwr(P("C7", "2"), "GND")
CV("C8", "100n", 248.92, 40.64); pwr(P("C8", "2"), "GND")
pwr(P("U1", "1"), "GND")
# EN: RC-затримка + кнопка RESET
W(P("U1", "3"), (213.36, 55.88), (213.36, 43.18), (195.58, 43.18))
RV("R9", "10k", 213.36, 35.56); psym("+3V3", P("R9", "1"), 90)
CV("C9", "1u", 205.74, 43.18); pwr(P("C9", "2"), "GND")
place("SW2", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_TL3342", 195.58, 48.26, rot=270,
      rpos=(191.0, 46.99), vpos=(190.5, 49.53))
pwr(P("SW2", "2"), "GND")
# IO0: підтяжка + кнопка BOOT
W(P("U1", "27"), (177.8, 60.96))
RV("R10", "10k", 177.8, 53.34); psym("+3V3", P("R10", "1"), 90)
place("SW3", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_SPST_TL3342", 177.8, 66.04, rot=270,
      rpos=(183.8, 64.77), vpos=(184.3, 67.31))
pwr(P("SW3", "2"), "GND")
# світлодіод статусу
W(P("U1", "38"), (209.55, 66.04)); RH("R11", "1k", 201.93, 66.04, flip=True)
place("D3", "Device:LED", "GREEN", "LED_SMD:LED_0603_1608Metric", 195.58, 66.04, rpos=(195.58, 63.5), vpos=(195.58, 68.58))
W(P("D3", "2"), P("R11", "2")); W(P("D3", "1"), (189.23, 66.04)); pwr((189.23, 66.04), "GND")
# зв'язки з іншими блоками
stub("U1", "39", "BAT_ADC")
for num, net in (("4", "BTN_UP"), ("5", "BTN_DOWN"), ("6", "BTN_OK"), ("12", "LORA_NRST"), ("17", "LORA_DIO1"),
                 ("18", "LORA_NSS"), ("19", "LORA_MOSI"), ("20", "LORA_SCK"), ("21", "LORA_MISO"), ("22", "LORA_BUSY"),
                 ("10", "OLED_SDA"), ("11", "OLED_SCL"), ("13", "USB_DN"), ("14", "USB_DP")):
    stub("U1", num, net)
# UART-роз'єм прямо на TXD0/RXD0
place("J4", "Connector_Generic:Conn_01x04", "UART", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
      279.4, 55.88, rpos=(281.5, 50.8), vpos=(281.5, 63.5), just="left")
W(P("U1", "37"), P("J4", "2")); W(P("U1", "36"), P("J4", "3"))
W(P("J4", "1"), (271.78, 53.34)); pwr((271.78, 53.34), "GND", 90)
W(P("J4", "4"), (271.78, 60.96)); pwr((271.78, 60.96), "+3V3", 270)
text("J4: 1 GND, 2 TX, 3 RX, 4 3V3", 262.0, 68.0, 1.0)
# кнопки меню
for i, (ref, val, net) in enumerate((("SW4", "UP", "BTN_UP"), ("SW5", "DOWN", "BTN_DOWN"), ("SW6", "OK", "BTN_OK"))):
    y = 118.11 + i * 7.62
    place(ref, "Switch:SW_Push", val, "Button_Switch_SMD:SW_SPST_TL3342", 190.5, y, rpos=(186.69, y - 3.81), vpos=(193.04, y - 3.81))
    W(P(ref, "1"), (182.88, y)); lab(net, (182.88, y), 180)
    W(P(ref, "2"), (198.12, y)); pwr((198.12, y), "GND")
text("Кнопки меню: на GND, внутрішні pull-up ESP32", 175.26, 141.0, 1.0)

# =====================================================================
# 3. ДИСПЛЕЙ
# =====================================================================
box(172, 152, 290, 197, "3. ДИСПЛЕЙ: OLED 0,96'' SSD1306, I2C")
place("J3", "Connector_Generic:Conn_01x04", "OLED SSD1306 I2C", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
      246.38, 172.72, rpos=(248.5, 170.18), vpos=(248.5, 172.72), just="left")
W(P("J3", "1"), (238.76, 170.18), (238.76, 165.1)); psym("GND", (238.76, 165.1), 90)
W(P("J3", "2"), (233.68, 172.72), (233.68, 167.64)); psym("+3V3", (233.68, 167.64), 90)
W(P("J3", "3"), (223.52, 175.26)); lab("OLED_SCL", (224.79, 175.26))
RV("R12", "4.7k", 223.52, 165.1, dnp=True, note="ставити, якщо на модулі немає підтяжок"); pwr(P("R12", "1"), "+3V3")
W(P("R12", "2"), (223.52, 175.26))
W(P("J3", "4"), (200.66, 177.8)); lab("OLED_SDA", (200.66, 177.8), 180)
RV("R13", "4.7k", 210.82, 165.1, dnp=True, note="ставити, якщо на модулі немає підтяжок"); pwr(P("R13", "1"), "+3V3")
W(P("R13", "2"), (210.82, 177.8))
text("R12, R13 перекреслені = не паяти (DNP): лише якщо на модулі немає підтяжок I2C", 175.26, 185.42, 1.0)
text("Порядок виводів GND/VCC/SCL/SDA звірити з конкретним модулем!", 175.26, 189.23, 1.0)

# =====================================================================
# 4. РАДІО
# =====================================================================
box(294, 15, 410, 197, "4. РАДІО: SX1262, TCXO 32 МГц, DC-DC")
place("U2", "RF:SX1262IMLTRT", "SX1262IMLTRT", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", 355.6, 99.06,
      rpos=(359.41, 128.27), vpos=(359.41, 130.81), just="left")
# живлення: три виводи на одну шину +3V3, розв'язка поруч
for n in ("1", "10", "11"):
    W(P("U2", n), (P("U2", n)[0], 60.96))
W((330.2, 60.96), (360.68, 60.96)); pwr((330.2, 60.96), "+3V3")
CV("C10", "10u", 340.36, 60.96, fp=C0805); pwr(P("C10", "2"), "GND")
CV("C11", "100n", 330.2, 60.96, note="біля VBAT/VBAT_IO (Semtech C18)"); pwr(P("C11", "2"), "GND")
pwr(P("U2", "2"), "GND")
# DC-DC: L1 між DCC_SW і VREG, C12 на VREG
W(P("U2", "7"), (378.46, 83.82), (378.46, 71.12), (398.78, 71.12))
W(P("U2", "9"), (386.08, 86.36), (386.08, 78.74))
LV("L1", "15u", 386.08, 71.12, flip=True, fp="Inductor_SMD:L_Coilcraft_LPS3010",
   note="LPS3010-153, DCR<=2 Ом, Idc>=100 мА (Semtech 5.1.5)")
CV("C12", "470n", 398.78, 71.12, note="Semtech C17"); pwr(P("C12", "2"), "GND")
# VR_PA: розв'язка + на дросель PA (блок 5)
W(P("U2", "24"), (403.86, 91.44)); lab("SX_VR_PA", (403.86, 91.44), 90)
CV("C13", "47n", 383.54, 91.44); pwr(P("C13", "2"), "GND")
CV("C14", "47p", 391.16, 91.44); pwr(P("C14", "2"), "GND")
for n, net in (("23", "RFO"), ("22", "RFI_N"), ("21", "RFI_P"), ("14", "LORA_BUSY"),
               ("15", "LORA_NRST"), ("13", "LORA_DIO1"), ("12", "SX_DIO2"), ("6", "TCXO_VCC"),
               ("18", "LORA_SCK"), ("16", "LORA_MISO"), ("17", "LORA_MOSI"), ("19", "LORA_NSS")):
    stub("U2", n, net)
# TCXO -> 220 Ом -> 10 пФ -> XTA
place("Y1", "Oscillator:TG2520SMN-xx.xxxxxxMhz-xxxxNM", "TG2520SMN 32MHz 1.8V",
      "Oscillator:Oscillator_SMD_SeikoEpson_TG2520SMN-xxx-xxxxxx-4Pin_2.5x2.0mm", 309.88, 83.82,
      rpos=(301.0, 92.71), vpos=(309.88, 97.79), note="clipped sine <=1,2 Vpp; напруга = SetDIO3AsTCXOCtrl")
RH("R14", "220", 320.04, 83.82, rpos=(323.85, 79.38), vpos=(323.85, 81.28)); CH("C16", "10p", 330.2, 83.82, rpos=(334.01, 79.38), vpos=(334.01, 81.28))
W(P("Y1", "3"), P("R14", "1")); W(P("R14", "2"), P("C16", "1")); W(P("C16", "2"), P("U2", "3"))
W(P("Y1", "4"), (309.88, 68.58), (317.5, 68.58)); W((309.88, 68.58), (309.88, 63.5)); lab("TCXO_VCC", (309.88, 63.5), 90)
CV("C15", "100n", 317.5, 68.58); pwr(P("C15", "2"), "GND"); flag((313.69, 68.58))
pwr(P("Y1", "2"), "GND")
text("TCXO живиться від DIO3 (SetDIO3AsTCXOCtrl).", 297.18, 140.97, 1.0)
text("Сигнал: TCXO -> R14 220 Ом -> C16 10 пФ -> XTA;", 297.18, 144.78, 1.0)
text("XTB не підключати (Semtech рис. 4-2).", 297.18, 148.59, 1.0)
text("L1 + C12: DC-DC SX1262 (DCC_SW -> VREG).", 297.18, 152.4, 1.0)

# =====================================================================
# 5. RF-ТРАКТ
# =====================================================================
box(10, 200, 290, 286, "5. RF-ТРАКТ 433 МГц: дросель PA, ФНЧ, RF-ключ, балун RX, антена")
TBD = "TBD 433"
YT = 233.68
W((25.4, YT), (41.91, YT)); lab("RFO", (25.4, YT), 180)
LV("L2", "47n", 33.02, YT - 7.62, note="дросель живлення PA (як L8 у DATALOGGER02); перевірити для 433")
W(P("L2", "1"), (33.02, YT - 10.16)); lab("SX_VR_PA", (33.02, YT - 10.16), 90)
LH("L3", TBD, 41.91, YT, note="узгодження PA, підбір NanoVNA/за ref-design 433-490")
W(P("L3", "2"), (66.04, YT)); lab("TX1", (50.8, YT), size=1.0)
CH("C29", TBD, 41.91, YT - 10.16, dnp=True, rpos=(45.72, YT - 13.6), vpos=(55.5, YT - 10.16), note="режектор 2-ї гармоніки: C29 || L3 резонує на 2f0 = 868 МГц (як C4 у Semtech AN1200.40, п. 3.1.3)")
W((41.91, YT), P("C29", "1")); W((49.53, YT), P("C29", "2"))
CV("C17", "6.8p", 58.42, YT, note="ФНЧ 5 порядку (Чебишев 0,1 дБ, зріз ~500 МГц, 50 Ом), C0G 2%; власний розрахунок"); pwr(P("C17", "2"), "GND")
LH("L4", "22n", 66.04, YT, note="ФНЧ")
W(P("L4", "2"), (88.9, YT)); lab("TX2", (74.93, YT), size=1.0)
CV("C18", "12p", 81.28, YT, note="ФНЧ, C0G 2%"); pwr(P("C18", "2"), "GND")
LH("L5", "22n", 88.9, YT, note="ФНЧ")
W(P("L5", "2"), (111.76, YT)); lab("TX3", (97.79, YT), size=1.0)
CV("C19", "6.8p", 104.14, YT, note="ФНЧ, C0G 2%"); pwr(P("C19", "2"), "GND")
CH("C20", "100p", 111.76, YT, note="розділовий")
place("U6", "pager:PE4259", "PE4259", "Package_TO_SOT_SMD:SOT-363_SC-70-6", 180.34, YT + 2.54,
      rpos=(186.0, 229.87), vpos=(186.69, 247.65), just="left", note="single-pin режим: вив.6 VDD=3,3 В, вив.4 CTRL=DIO2; CTRL=1 (TX) -> RFC-RF1, CTRL=0 (RX) -> RFC-RF2 (pSemi DOC-03694, табл. 5)")
W(P("C20", "2"), P("U6", "1")); lab("SW_RF1", (128.27, YT), size=1.0)
# живлення ключа
W(P("U6", "6"), (180.34, 215.9), (172.72, 215.9))
RV("R16", "100", 180.34, 208.28, note="Semtech R4"); psym("+3V3", P("R16", "1"), 90)
CV("C22", "1n", 172.72, 215.9, note="Semtech C14"); pwr(P("C22", "2"), "GND"); flag((176.53, 215.9))
pwr(P("U6", "2"), "GND")
# керування ключем від DIO2
W(P("U6", "4"), (205.74, YT + 5.08))
CV("C21", "1n", 200.66, YT + 5.08, note="Semtech C15"); pwr(P("C21", "2"), "GND")
RH("R15", "100", 205.74, YT + 5.08, flip=True, note="Semtech R3")
W(P("R15", "1"), (218.44, YT + 5.08)); lab("SX_DIO2", (218.44, YT + 5.08))
# антена: розділовий C26 + П-узгодження C27/L8/C28
YA = 223.52
W(P("U6", "5"), (193.04, YT + 2.54), (193.04, YA), (198.12, YA)); lab("SW_RFC", (193.04, 228.6), 90, size=1.0)
CH("C26", "100p", 198.12, YA, note="розділовий")
W(P("C26", "2"), (223.52, YA)); lab("ANT_M1", (215.9, YA), size=1.0)
CV("C27", TBD, 213.36, YA, dnp=True, note="π-узгодження антени"); pwr(P("C27", "2"), "GND")
LH("L8", "0R", 223.52, YA, note="π-узгодження: перемичка 0 Ом до налаштування")
place("J5", "Connector:Conn_Coaxial", "SMA 50 Ом", "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount", 251.46, YA,
      rpos=(254.0, 218.44), vpos=(254.0, 220.98), just="left")
W(P("L8", "2"), P("J5", "1")); lab("ANT", (240.03, YA), size=1.0)
CV("C28", TBD, 238.76, YA, dnp=True, note="π-узгодження антени"); pwr(P("C28", "2"), "GND")
pwr(P("J5", "2"), "GND")
# прийом: RF2 -> C23 -> LC-балун -> RFI_P / RFI_N
YR, YN = 254.0, 269.24
W(P("U6", "3"), (160.02, YT + 5.08), (160.02, YR), (156.21, YR))
CH("C23", "100p", 148.59, YR, flip=True, note="розділовий"); lab("SW_RF2", (160.02, 246.38), 90, size=1.0)
W(P("C23", "2"), (138.43, YR)); W((142.24, YR), (142.24, YN), (138.43, YN)); lab("RX_IN", (142.24, 261.62), 90, size=1.0)
CH("C24", TBD, 130.81, YR, flip=True, note="LC-балун RX: підбір під 433 МГц")
LH("L6", TBD, 130.81, YN, flip=True, note="LC-балун RX")
W(P("C24", "2"), (106.68, YR)); lab("RFI_P", (106.68, YR), 180)
CV("C25", TBD, 119.38, YR, dnp=True, note="LC-балун RX"); pwr(P("C25", "2"), "GND")
W(P("L6", "2"), (106.68, YN)); lab("RFI_N", (106.68, YN), 180)
LV("L7", TBD, 114.3, YN, dnp=True, note="LC-балун RX"); pwr(P("L7", "2"), "GND")
text("Передача: RFO -> L3 -> ФНЧ L4/L5 + C17-C19 -> C20 -> U6 RF1 -> RFC -> антена.", 165.1, 256.54, 1.1)
text("Прийом: антена -> U6 RFC -> RF2 -> C23 -> LC-балун (C24, L6) -> RFI_P / RFI_N.", 165.1, 260.35, 1.1)
text("Балун за Semtech (DS SX1268, рис. 14-1): L6 = 0 Ом, на місце C24 - котушка, C25 - конденсатор.", 165.1, 263.5, 1.1)
text("ФНЧ - власний розрахунок: Чебишев 0,1 дБ; розрахункове послаблення 2f0 - 26 дБ, 3f0 - 46 дБ.", 165.1, 266.7, 1.1)
text("TBD 433 - підібрати векторним аналізатором: офіційних номіналів Semtech для 433 МГц у відкритому доступі немає.", 165.1, 270.51, 1.1)
text("Без вимірювань не вмикати +22 dBm: для SRD 433 МГц в Україні - 1 мВт.", 165.1, 274.32, 1.1)

# =====================================================================
# Легенда
# =====================================================================
box(294, 200, 410, 250, "Як читати схему")
for i, s in enumerate((
        "Деталі обв'язки стоять біля виводів своєї мікросхеми й з'єднані проводами.",
        "Мітка (напис на кінці проводу, напр. LORA_SCK) з'єднує однойменні точки",
        "  в різних блоках: SPI, I2C, USB, кнопки, RF-сигнали між SX1262 і трактом.",
        "Символи GND / +3V3 / VBUS - загальні шини живлення.",
        "Перекреслений елемент = DNP (не паяти): місце на платі є, ставиться",
        "  лише при налаштуванні (C25, C27, C28, C29, L7 - RF-налаштування; R12, R13 - I2C).",
        "Крапка - з'єднання проводів; перетин без крапки - не з'єднані.",
        "TBD 433 - номінал ще не підібраний (див. блок 5).")):
    text(s, 297.18, 206.5 + i * 4.3, 1.1)

# кріпильні отвори M2,5 (без металізації)
text("H1-H4: кріпильні отвори M2,5 без металізації", 297.18, 243.3, 1.1)
for i_, x_ in enumerate((352.0, 366.0, 380.0, 394.0)):
    place(f"H{i_ + 1}", "Mechanical:MountingHole", "M2.5", "MountingHole:MountingHole_2.7mm_M2.5", x_, 244.5,
          rpos=(x_ + 2.6, 243.2), vpos=(x_ + 2.6, 245.8), just="left")

# ---------- постобробка: розбити дроти в точках дотику, поставити вузли ----------
def on_seg(p, a, b):
    if a[0] == b[0] == p[0]: return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if a[1] == b[1] == p[1]: return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False

pts = {(x, y) for x, y, *_ in PINPTS} | {(l[1], l[2]) for l in LABELS}
for a, b in WIRES: pts |= {a, b}
segs, changed = list(dict.fromkeys(WIRES)), True
while changed:
    changed = False
    for i, (a, b) in enumerate(segs):
        cut = next((p for p in pts if on_seg(p, a, b)), None)
        if cut:
            segs[i:i + 1] = [(a, cut), (cut, b)]; changed = True; break
ends = {}
for a, b in segs:
    for p in (a, b): ends[p] = ends.get(p, 0) + 1
pinat = {}
for x, y, *_ in PINPTS: pinat[(x, y)] = pinat.get((x, y), 0) + 1
junctions = [p for p, n in ends.items() if n + pinat.get(p, 0) >= 3]
# виводи, до яких нічого не підходить -> «не підключено»
lab_pts = {(l[1], l[2]) for l in LABELS}
for x, y, ref, num in PINPTS:
    if ref.startswith("#"): continue
    if (x, y) in ends or (x, y) in lab_pts or pinat[(x, y)] > 1: continue
    NCS.append((x, y))

items = [f'(wire (pts (xy {fmt(a[0])} {fmt(a[1])}) (xy {fmt(b[0])} {fmt(b[1])})) (stroke (width 0) (type default)) (uuid "{uid()}"))' for a, b in segs]
items += [f'(junction (at {fmt(x)} {fmt(y)}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))' for x, y in junctions]
items += [f'(no_connect (at {fmt(x)} {fmt(y)}) (uuid "{uid()}"))' for x, y in NCS]
for net, x, y, d, size in LABELS:
    just = "left" if d in (0, 90) else "right"
    items.append(f'(label "{net}" (at {fmt(x)} {fmt(y)} {d}) (effects (font (size {size} {size})) (justify {just} bottom)) (uuid "{uid()}"))')
items += TEXTS

# ---------- запис ----------
lib_txt = "\n".join(LIBSYMS[k] for k in sorted(LIBSYMS))
sch = f'''(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid "{ROOT_UUID}") (paper "A3")
(title_block (title "LoRa mesh-пейджер: ESP32-S3 + SX1262, 433 МГц") (date "2026-11-11") (rev "0.4")
  (company "НУ «Львівська політехніка», ЕЛ-12") (comment 1 "Батрак С. О.; керівник Качурак Ю. М.")
  (comment 2 "Чернетка для навчання: RF-номінали TBD, перед замовленням PCB перевірити"))
(lib_symbols
{lib_txt}
)
{chr(10).join(items)}
{chr(10).join(symbols)}
(sheet_instances (path "/" (page "1")))
(embedded_fonts no)
)
'''
(OUT / f"{NAME}.kicad_sch").write_text(sch, encoding="utf-8")
pro = OUT / f"{NAME}.kicad_pro"
if not pro.exists():   # не затирати налаштування плати (net classes, правила), які пише gen_pcb.py
    pro.write_text('{"meta": {"filename": "%s.kicad_pro", "version": 3}, "sheets": [["%s", "Root"]]}\n' % (NAME, ROOT_UUID), encoding="utf-8")
(OUT / "pager.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") (generator_version "9.0")\n' + PE4259 + "\n)\n", encoding="utf-8")
(OUT / "sym-lib-table").write_text('(sym_lib_table (version 7)\n  (lib (name "pager") (type "KiCad") (uri "${KIPRJMOD}/pager.kicad_sym") (options "") (descr "PE4259"))\n)\n', encoding="utf-8")
import csv
with open(OUT / "BOM_draft.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["Ref", "Value", "Footprint", "Note"])
    for b in sorted(BOM, key=lambda b: (re.sub(r"\d", "", b[0]), int(re.sub(r"\D", "", b[0]) or 0))):
        w.writerow(b)
print("ok", len(BOM), "parts", len(segs), "wires", len(LABELS), "labels", len(junctions), "junctions", len(NCS), "nc")
