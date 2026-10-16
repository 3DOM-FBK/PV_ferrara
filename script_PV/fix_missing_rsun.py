"""
Find and recompute ONLY the missing r.sun daily maps.

    python3 fix_missing_rsun.py --dataFolder /root/PV_ferrara/FE_data/output            # report only
    python3 fix_missing_rsun.py --dataFolder /root/PV_ferrara/FE_data/output --run      # recompute

Uses the same inputs and naming as generateRsunParallel.py:
    dtm/<tile>_dtm.tif, aspect/<tile>_aspect.tif, slope/<tile>_slope.tif,
    tile/<tile>_tile.shp, horizon/<tile>_dtm_3x3_merge_horangle_<ang>
    -> rSun/<tile>/<tile>_rSun_<month>_<day>

Each parallel worker uses its own GRASS mapset (no lock conflicts), every
command is checked, and a failed day is retried once.
"""
import argparse
import calendar
import multiprocessing as mp
import os
import shutil
import subprocess
import sys

LOCATION = "/home/FerraraLocation"
PERMANENT = os.path.join(LOCATION, "PERMANENT")
LINKE_FOLDER = "/root/PV_ferrara/FE_data/linkeMap/linkeMap_7791"
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
YEAR = 2022


def grass(mapset, *args, check=True):
    cmd = ["grass", mapset, "-f", "--exec"] + list(args)
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True)
    if check and r.returncode != 0:
        raise RuntimeError("FAILED: " + " ".join(args) + "\n" + r.stdout[-2000:])
    return r


def all_days():
    doy = 0
    for m, month in enumerate(MONTHS, start=1):
        for day in range(1, calendar.monthrange(YEAR, m)[1] + 1):
            doy += 1
            yield month, day, doy


def missing_days(data_folder, tile):
    folder = os.path.join(data_folder, "rSun", tile)
    present = set(os.listdir(folder)) if os.path.isdir(folder) else set()
    out = []
    for month, day, doy in all_days():
        name = "{}_rSun_{}_{}".format(tile, month, day)
        path = os.path.join(folder, name)
        if name not in present or os.path.getsize(path) == 0:
            out.append((month, day, doy, name))
    return out


def worker_init(args):
    global W_MAPSET, W_ARGS
    W_ARGS = args
    W_MAPSET = os.path.join(LOCATION, "fix_{}".format(os.getpid()))
    if not os.path.isdir(W_MAPSET):
        subprocess.run(["grass", "-e", "-c", W_MAPSET], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    grass(W_MAPSET, "g.region", "vector=tile@PERMANENT", "align=" + args["dtm"] + "@PERMANENT")


def compute_day(job):
    month, day, doy, name = job
    a = W_ARGS
    for attempt in (1, 2):
        try:
            grass(W_MAPSET, "r.sun", "--overwrite",
                  "elevation=" + a["dtm"] + "@PERMANENT",
                  "aspect=" + a["aspect"] + "@PERMANENT",
                  "slope=" + a["slope"] + "@PERMANENT",
                  "horizon_basename=" + a["hor_base"],
                  "horizon_step=" + str(a["step"]),
                  "linke=" + month + ".tif@PERMANENT",
                  "day=" + str(doy), "glob_rad=" + name)
            grass(W_MAPSET, "r.out.gdal", "--overwrite", "input=" + name,
                  "output=" + os.path.join(a["out"], name), "format=GTiff")
            grass(W_MAPSET, "g.remove", "-f", "type=raster", "name=" + name)
            return None
        except RuntimeError as e:
            err = str(e)
    return name + "\n" + err


def fix_tile(data_folder, tile, todo, step, nproc):
    prj = PERMANENT
    dtm = tile + "_dtm.tif"
    aspect = tile + "_aspect"
    slope = tile + "_slope"
    grass(prj, "r.import", "--overwrite", "input=" + os.path.join(data_folder, "dtm", tile + "_dtm.tif"), "output=" + dtm)
    grass(prj, "r.import", "--overwrite", "input=" + os.path.join(data_folder, "aspect", tile + "_aspect.tif"), "output=" + aspect)
    grass(prj, "r.import", "--overwrite", "input=" + os.path.join(data_folder, "slope", tile + "_slope.tif"), "output=" + slope)
    grass(prj, "v.import", "--overwrite", "input=" + os.path.join(data_folder, "tile", tile + "_tile.shp"), "output=tile")

    hor_base = tile + "_dtm_3x3_merge_horangle"
    hor_files = sorted(f for f in os.listdir(os.path.join(data_folder, "horizon"))
                       if f.startswith(hor_base + "_") and not f.endswith(".aux.xml"))
    if len(hor_files) != 360 // step:
        raise RuntimeError("{}: {} horizon maps, expected {}".format(tile, len(hor_files), 360 // step))
    for h in hor_files:
        grass(prj, "r.import", "--overwrite", "input=" + os.path.join(data_folder, "horizon", h), "output=" + h)

    out = os.path.join(data_folder, "rSun", tile)
    os.makedirs(out, exist_ok=True)
    args = dict(dtm=dtm, aspect=aspect, slope=slope, hor_base=hor_base, step=step, out=out)

    with mp.Pool(nproc, initializer=worker_init, initargs=(args,)) as p:
        failures = [r for r in p.map(compute_day, todo) if r]

    grass(prj, "g.remove", "-f", "type=raster", "name=" + ",".join([dtm, aspect, slope] + hor_files))
    grass(prj, "g.remove", "-f", "type=vector", "name=tile")
    for d in os.listdir(LOCATION):
        if d.startswith("fix_"):
            shutil.rmtree(os.path.join(LOCATION, d), ignore_errors=True)
    return failures


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataFolder", required=True)
    ap.add_argument("--horizon_step", type=int, default=10)
    ap.add_argument("--nproc", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--run", action="store_true", help="recompute missing days (default: report only)")
    a = ap.parse_args()

    tiles = sorted(f[:-len("_tile.shp")] for f in os.listdir(os.path.join(a.dataFolder, "tile"))
                   if f.endswith("_tile.shp"))
    report = {t: missing_days(a.dataFolder, t) for t in tiles}
    bad = {t: m for t, m in report.items() if m}

    print("tiles: {}   complete: {}   incomplete: {}".format(len(tiles), len(tiles) - len(bad), len(bad)))
    for t, m in bad.items():
        months = sorted(set(x[0] for x in m), key=MONTHS.index)
        print("  {}: {} missing  ({})".format(t, len(m), ", ".join(months)))

    if not bad:
        sys.exit(0)
    if not a.run:
        print("\nRun again with --run to recompute only these days.")
        sys.exit(1)

    if not os.path.isdir(PERMANENT):
        subprocess.run(["grass", "-e", "-c", "epsg:7791", LOCATION], check=True)
    for r in os.listdir(LINKE_FOLDER):               # make sure linke maps are in PERMANENT
        if ".xml" not in r:                          # same filter as generateRsunParallel.py
            grass(PERMANENT, "r.import", "--overwrite", "input=" + os.path.join(LINKE_FOLDER, r),
                  "output=" + r.split("_cut_scaled")[0] + ".tif")

    all_failures = []
    for i, (t, m) in enumerate(bad.items(), 1):
        print("[{}/{}] {}: recomputing {} days ...".format(i, len(bad), t, len(m)), flush=True)
        all_failures += fix_tile(a.dataFolder, t, m, a.horizon_step, a.nproc)

    still = {t: missing_days(a.dataFolder, t) for t in bad}
    still = {t: m for t, m in still.items() if m}
    if still or all_failures:
        print("\nSTILL MISSING:")
        for t, m in still.items():
            print("  {}: {}".format(t, len(m)))
        for f in all_failures[:5]:
            print("----\n" + f)
        sys.exit(1)
    print("\nAll tiles now have 365 daily maps.")
