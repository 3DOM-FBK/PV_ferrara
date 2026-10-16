#!/usr/bin/env bash
# =====================================================================
# Quick re-run: correct monthly + annual r.sun radiation
# Reuses existing dtm/, tile/, horizon/ (horizon is NOT recomputed).
#
# Fixes applied:
#   - aspect regenerated in GRASS convention (0 = east, counterclockwise)
#     instead of compass azimuth  -> correct orientation of tilted surfaces
#   - flat cells get aspect 0 instead of nodata -> no NULL on flat roofs
#   - slope/aspect computed at tile edges        -> no seams in the mosaic
#   - stale GRASS maps cleaned, yearly sum without double counting,
#     yearly mosaic added
#
# Run from the folder containing the (patched) python scripts:
#   bash rerun_rsun.sh
# =====================================================================
set -euo pipefail

# ---------------- settings: check these ----------------
DATA=/root/PV_ferrara/FE_data/output          # pipeline output folder
GRASS_MAPSET=/home/FerraraLocation/PERMANENT   # GRASS location used by the scripts
HORIZON_STEP=10                                # must match the existing horizon maps
START_STEP=${START_STEP:-1}                    # e.g. START_STEP=4 bash rerun_rsun.sh  to resume after r.sun
# --------------------------------------------------------

export LC_ALL=C.UTF-8      # month names from strftime must be English (linke maps, file names)
cd "$(dirname "$0")"
step() { echo; echo "=== $(date '+%H:%M:%S') $* ==="; }
fail() { echo "ERROR: $*" >&2; exit 1; }

# ---------------- 0. sanity checks ----------------
step "0. Checks"
command -v gdaldem >/dev/null || fail "gdaldem not found (install gdal-bin)"
command -v grass   >/dev/null || fail "grass not found"
for d in dtm tile horizon; do [ -d "$DATA/$d" ] || fail "missing $DATA/$d"; done
if [ ! -d "$GRASS_MAPSET" ]; then
    # the location lives inside the container, so it is gone after every new `docker run`
    echo "creating GRASS location $(dirname "$GRASS_MAPSET") (EPSG:7791)"
    grass -e -c epsg:7791 "$(dirname "$GRASS_MAPSET")"
fi
[ -d "$GRASS_MAPSET" ] || fail "could not create GRASS mapset $GRASS_MAPSET"

N_TILES=$(ls "$DATA"/tile/*_tile.shp | wc -l)
N_HOR_EXPECTED=$(( N_TILES * 360 / HORIZON_STEP ))
N_HOR=$(ls "$DATA"/horizon | grep -v '\.aux\.xml$' | wc -l)
echo "tiles: $N_TILES   horizon maps: $N_HOR (expected $N_HOR_EXPECTED)"
[ "$N_HOR" -eq "$N_HOR_EXPECTED" ] || fail "horizon maps incomplete"

# ---------------- 1. regenerate slope + aspect ----------------
if [ "$START_STEP" -le 1 ]; then
step "1. Regenerate slope and aspect (GRASS convention, edges, flat=0)"
rm -rf "$DATA/aspect_old" "$DATA/slope_old"
[ -d "$DATA/aspect" ] && mv "$DATA/aspect" "$DATA/aspect_old"
[ -d "$DATA/slope" ]  && mv "$DATA/slope"  "$DATA/slope_old"
mkdir -p "$DATA/aspect" "$DATA/slope"
for f in "$DATA"/dtm/*_dtm.tif; do
    base=$(basename "$f" _dtm.tif)
    gdaldem aspect "$f" "$DATA/aspect/${base}_aspect.tif" -trigonometric -zero_for_flat -compute_edges -q
    gdaldem slope  "$f" "$DATA/slope/${base}_slope.tif"   -compute_edges -q
done
echo "aspect: $(ls "$DATA"/aspect/*.tif | wc -l)  slope: $(ls "$DATA"/slope/*.tif | wc -l)"
fi

# ---------------- 2. clean GRASS mapset ----------------
if [ "$START_STEP" -le 3 ]; then
step "2. Remove leftover maps from the GRASS mapset"
grass "$GRASS_MAPSET" -f --exec g.remove -f type=raster,vector pattern='*' || true

# ---------------- 3. r.sun daily maps ----------------
step "3. r.sun daily maps (longest step)"
python3 generateRsunParallel.py --dataFolder "$DATA" --outFolder "$DATA/rSun" --horizon_step "$HORIZON_STEP"
fi

# ---------------- 3b. recompute any missing daily maps ----------------
step "3b. Check / recompute missing daily maps"
python3 fix_missing_rsun.py --dataFolder "$DATA" --horizon_step "$HORIZON_STEP" --run

# ---------------- 4. monthly sums ----------------
step "4. Monthly sums"
rm -rf "$DATA/rSun_sum" && mkdir "$DATA/rSun_sum"
python3 generate_Rsun_MonthMaps.py --dataFolder "$DATA" --outFolder "$DATA/rSun_sum" --process rsun_month --dataset_nr 0

# ---------------- 5. annual sums ----------------
step "5. Annual sums"
python3 generate_Rsun_MonthMaps.py --dataFolder "$DATA" --outFolder "$DATA/rSun_sum" --process rsun_year --dataset_nr 0
for d in "$DATA"/rSun_sum/*/; do
    n=$(ls "$d" | grep -v '\.aux\.xml$' | wc -l)
    [ "$n" -eq 13 ] || fail "$(basename "$d"): $n maps instead of 12 months + year"
done
echo "all tiles have 12 monthly + 1 yearly map"

# ---------------- 6. mosaics ----------------
step "6. Monthly + yearly mosaics"
sed -i "s#^    dataFolder = \".*\"#    dataFolder = \"$DATA\"#" generate_mosaic4months.py
python3 generate_mosaic4months.py
n=$(ls "$DATA"/mosaic_month/*.tif | wc -l)
[ "$n" -eq 13 ] || fail "$n mosaics instead of 13"

# ---------------- 7. quick plausibility check ----------------
step "7. Yearly mosaic statistics [Wh/m2/year]"
gdalinfo -stats "$DATA/mosaic_month/year_mosaic.tif" | grep -E 'STATISTICS_(MINIMUM|MAXIMUM|MEAN)'
echo
echo "Done. Old slope/aspect kept in $DATA/slope_old and $DATA/aspect_old (delete when satisfied)."
