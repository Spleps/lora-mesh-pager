"""Продовження mesh_experiment_run4.py з прогону, на якому він перервався.
Ті самі seed (202611090000+i) і те саме налаштування settings[i % 576], тому результат
збігається з безперервним запуском. Рахує у 3 процеси, потім сортує trials.csv за seed."""
import csv, datetime, itertools, json, time
from multiprocessing import Pool
from pathlib import Path
import mesh_experiment_run4 as m

DEST = m.DEST
SETTINGS = list(itertools.product([5,10,20,40],[7,9,12],[30,120,600],[1,3],[.01,.1],[1,5],["corridor","campus"]))
TOTAL = len(SETTINGS) * 48
ORIGIN = 202611090000

def run(i):
    return m.trial(ORIGIN + i, *SETTINGS[i % len(SETTINGS)])

def main():
    path = DEST / "trials.csv"
    rows = list(csv.reader(path.open()))
    header, done = rows[0], {int(r[0]) - ORIGIN: r for r in rows[1:] if len(r) == len(rows[0])}
    todo = [i for i in range(TOTAL) if i not in done]
    print("RESUME done", len(done), "todo", len(todo), flush=True)
    t0 = time.monotonic(); last = t0
    with Pool(3) as p, (DEST / "trials_resume.csv").open("a", newline="") as f:
        w = csv.writer(f)
        for k, row in enumerate(p.imap_unordered(run, todo, chunksize=8), 1):
            w.writerow(row); done[row[0] - ORIGIN] = row
            if time.monotonic() - last > 60:
                f.flush(); last = time.monotonic()
                st = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "trials": len(done), "planned": TOTAL}
                (DEST / "status.json").write_text(json.dumps(st, indent=2)); print("SIMULATION_PROGRESS", json.dumps(st), flush=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(header)
        for i in range(TOTAL): w.writerow(done[i])
    md = json.loads((DEST / "metadata.json").read_text())
    md.update(complete_factorial_design=True, trials=len(done), resumed_from=TOTAL - len(todo),
              finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              note="Перервано разом із SSH-сесією; дораховано тим самим генератором seed у 3 процеси.")
    (DEST / "metadata.json").write_text(json.dumps(md, indent=2, ensure_ascii=False))
    print("SIMULATION_FINISHED", len(done), round(time.monotonic() - t0), "s", flush=True)

if __name__ == "__main__":
    main()
