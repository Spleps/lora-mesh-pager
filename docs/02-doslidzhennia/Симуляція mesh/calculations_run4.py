"""Independent, reproducible engineering calculations, not radio measurements."""
import csv, json, math, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'audit_run4'
def airtime(sf,pl,bw,cr=1,preamble=8,crc=1,ih=0):
    de=int((2**sf/bw)>=0.016)
    symbols=8+max(math.ceil((8*pl-4*sf+28+16*crc-20*ih)/(4*(sf-2*de)))*(cr+4),0)
    return (preamble+4.25+symbols)*2**sf/bw
rows=[]
for sf in [7,9,12]:
    for pl in [16,32,64,128,240]:
        t=airtime(sf,pl,125000)
        rows.append(dict(sf=sf,phy_payload_bytes=pl,bw_hz=125000,cr='4/5',crc=True,explicit_header=True,preamble_symbols=8,toa_ms=t*1000,max_packets_per_hour_at_1percent=math.floor(36/t),max_packets_per_hour_at_10percent=math.floor(360/t)))
with (OUT/'airtime_calculations.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
# Independently verify common manually calculable boundary cases.
assert abs(airtime(7,16,125000)-.051456)<1e-12
assert abs(airtime(12,64,125000)-2.793472)<1e-12
data={'frequency_hz':433920000,'wavelength_m':299792458/433920000,'quarter_wave_m':299792458/433920000/4,
      'rf_word_433920000':round(433920000*2**25/32000000),
      'power_22dbm_mw':10**2.2,'inductor_10nh_reactance_ohm':2*math.pi*433920000*10e-9,
      'capacitor_10pf_reactance_ohm':1/(2*math.pi*433920000*10e-12),
      'zero_loss_300_upper95_exact':1-.05**(1/300),'zero_loss_300_rule_of_three':3/300,
      'battery_hours_assumed':(1*3.7*.85)/((.040+.005+.010)*3.3),
      'warning':'All computations are illustrative; 1% and 10% airtime budgets are scenarios, not claims about Ukrainian SRD433 duty-cycle requirements.'}
(OUT/'engineering_calculations.json').write_text(json.dumps(data,indent=2))
print(json.dumps(data,indent=2))
md='Параметри власного ToA-розрахунку: BW125 кГц, CR4/5, explicit header, CRC увімкнено, преамбула8 символів; DE=1 при тривалості символу не менше16 мс. PL — повна PHY payload, тобто текст разом із мережевими заголовками. Формула звірена з Semtech, розд.6.1.4; це розрахунок, не затримка мережі.\n\n'
md+='| SF | PL16 байтів, мс | PL64 байти, мс | PL240 байтів, мс | ПакетівPL64 за годину при1% /10% |\n|---|---|---|---|---|\n'
for sf in [7,9,12]:
    vals=[next(r for r in rows if r['sf']==sf and r['phy_payload_bytes']==p) for p in [16,64,240]]
    md+=f'| {sf} | {vals[0]["toa_ms"]:.3f} | {vals[1]["toa_ms"]:.3f} | {vals[2]["toa_ms"]:.3f} | {vals[1]["max_packets_per_hour_at_1percent"]} / {vals[1]["max_packets_per_hour_at_10percent"]} |\n'
md+='\nБюджети1% і10% тут лише ілюстративні сценарії; вони не підміняють рядок103 української таблиці. Повторення пакета кожним ретранслятором витрачає його окремий ефірний бюджет. До ToA додаються backoff, черга, ACK і можливі повтори.\n\n'
md+=f'Слово синтезатора для433,92 МГц за32-МГц опорою: {data["rf_word_433920000"]} (0x{data["rf_word_433920000"]:08X}). Точна одностороння95% межа втрати для0/300 незалежних втрат: {data["zero_loss_300_upper95_exact"]*100:.3f}%; rule-of-three≈1%.\n'
(OUT/'calculations_section.md').write_text(md)
