"""Синхронізує готову плату зі схемою БЕЗ перетрасування: зв'язки посадкове місце↔символ (UUID) і назви кіл.
Працює, лише якщо з'єднання в схемі не змінювались (перевіряється за складом виводів кожного кола).
Запуск: python3 tools/sync_pcb.py   (нетлист: route/sch.net з kicad-cli sch export netlist)"""
import sys
from pathlib import Path
import pcbnew
sys.path.insert(0, str(Path(__file__).parent)); from netlist import load
proj = Path(__file__).resolve().parent.parent
comps, nets = load(proj / "route" / "sch.net")
b = pcbnew.LoadBoard(str(proj / "lora-pager.kicad_pcb"))
# 1) зв'язок посадкових місць із символами
for fp in b.GetFootprints():
    ref = fp.GetReference(); c = comps[ref]
    fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"]))
    fp.SetValue(c["value"])
    for k, v in c.get("fields", {}).items():      # користувацькі поля (Note) — інакше DRC «parity» видає помилку
        if k in ("Reference", "Value", "Footprint", "Datasheet", "Description"): continue
        if fp.HasField(k): fp.GetField(k).SetText(v)
        else:
            f = pcbnew.PCB_FIELD(fp, pcbnew.FIELD_T_USER, k); f.SetText(v); f.SetVisible(False); fp.Add(f)
# 2) назви кіл за складом виводів
pcbset = {}
for fp in b.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() > 0:
            pcbset.setdefault(pad.GetNetname(), set()).add((fp.GetReference(), pad.GetNumber()))
want = {frozenset(v): k for k, v in nets.items()}
ren = 0
for old, pins in pcbset.items():
    new = want.get(frozenset(pins))
    assert new, f"коло {old} не збігається зі схемою: {sorted(pins)}"
    if new != old:
        b.FindNet(old).SetNetname(new); ren += 1
b.Save(str(proj / "lora-pager.kicad_pcb"))
print("footprints:", len(b.GetFootprints()), "renamed nets:", ren)
