import os, shutil
import subprocess, shlex
from subprocess import Popen, PIPE
from calendar import monthrange
import datetime
from multiprocessing import Process, Pool
import multiprocessing as mp
import timeit
import time
import sys
import argparse

MAX_PROCESSOR = mp.cpu_count() - 2
#MAX_PROCESSOR = 4

###################################################################
# This function run shell command
#
###################################################################
def run_grass_cmd(cmd):
    p = subprocess.run(shlex.split(cmd))


###################################################################
# This function create new Location and PERMANENT Mapset
#
###################################################################
def create_project(coord_system_code, location_name):
    if ( not os.path.isdir(location_name) ):
        cmd = "grass -e -c epsg:" + str(coord_system_code) + " " + location_name
        run_grass_cmd(cmd)

    return os.path.join(location_name, "PERMANENT")


###################################################################
# This function import raster
#
###################################################################
def import_raster(inFile, outName, prjPath):
    cmd = "grass " + prjPath + " --exec r.import --overwrite input=" + inFile + " output=" + outName

    run_grass_cmd(cmd)

    return outName


###################################################################
# This function import vector
#
###################################################################
def import_vector(inFile, outName, prjPath):
    cmd = "grass " + prjPath + " --exec v.import --overwrite input=" + inFile + " output=" + outName

    run_grass_cmd(cmd)

    return outName


###################################################################
# This function set grass region
#
###################################################################
def set_region(raster_name, res, prjPath, region_type):
    cmd = "grass " + prjPath + " --exec g.region " + region_type + "=" + raster_name + " res=" + str(res)

    run_grass_cmd(cmd)


###################################################################
# This function compute r.sun function
#
###################################################################
def compute_rSun(dtm, horizon, step, ascpect, slope, month, day, outName):
    cmd = "grass " + prjPath + " -f --exec r.sun --overwrite elevation=" + dtm + " horizon_basename=" + horizon + " horizon_step=" + str(step) + " aspect=" + ascpect + " slope=" + slope + " linke=" + month + ".tif day=" + str(day) + " glob_rad=" + outName

    run_grass_cmd(cmd)


###################################################################
# This function prepare data for r.sun function
#
###################################################################
def process_data(inputData):
    compute_rSun(inputData[0], inputData[1], inputData[2], inputData[3], inputData[4], inputData[5], inputData[6], inputData[7])


###################################################################
# This function create folder to save all output
#
###################################################################
def check_outfolder(dataFolder):
    outFolder = os.path.join(dataFolder, "rSun")

    if (os.path.isdir(outFolder)):
        shutil.rmtree(outFolder)
    
    os.mkdir(outFolder)

    return outFolder


###################################################################
# This function create folder remove input raster
#
###################################################################
def remove_raster(list_rasterName, prjPath):
    cmd = "grass " + prjPath + " -f --exec g.remove -f type=raster name=" + list_rasterName

    run_grass_cmd(cmd)


###################################################################
# This function create folder remove input raster
#
###################################################################
def remove_vector(list_vectorName, prjPath):
    cmd = "grass " + prjPath + " -f --exec g.remove -f type=vector name=" + list_vectorName

    run_grass_cmd(cmd)


###################################################################
# This function export rSun maps
#
###################################################################
def export_rSun_map(rSun_name, outFolder):
    cmd = "grass " + prjPath + " --exec r.out.gdal input=" + rSun_name + " output=" + os.path.join(outFolder, rSun_name) + " format=GTiff"

    run_grass_cmd(cmd)


###################################################################
# This function split array a in n part
#
###################################################################
def split(a, n):
    k, m = divmod(len(a), n)
    return (a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))


###################################################################
# This function prepare data to r.sun
#
###################################################################
def prepare_data(f, prjPath, dataFolder, horizon_list, horizon_step, outFolder):
        dtm_raster = import_raster( os.path.join(dataFolder, "dtm", f ), f, prjPath)
        aspect_raster = import_raster( os.path.join(dataFolder, "aspect", f.replace("_dtm.tif", "_aspect.tif") ), f.replace("_dtm.tif", "_aspect"), prjPath)
        slope_raster = import_raster( os.path.join(dataFolder, "slope", f.replace("_dtm.tif", "_slope.tif") ), f.replace("_dtm.tif", "_slope"), prjPath)
        tile_vector = import_vector( os.path.join(dataFolder, "tile", f.replace("_dtm.tif", "_tile.shp") ), "tile", prjPath)

        """
        Search horizon raster to import
        """
        subString = f.replace("_dtm.tif", "")
        horizon_rasters = [string for string in horizon_list if subString in string]
        raster_list = dtm_raster + "," + aspect_raster + "," + slope_raster
        for count, horizon_raster in enumerate(horizon_rasters):
            h_raster = import_raster( os.path.join(dataFolder, "horizon", horizon_raster ), horizon_raster, prjPath)
            raster_list = raster_list + "," + h_raster
        
        """
        Set region
        """
        set_region(tile_vector, 1, prjPath, "vector")

        """
        Set base name of out raster map
        """
        rSun_baseName = f.replace("_dtm.tif", "_rSun_")

        """
        Set basename of horizon maps
        """
        horizon_baseName = f.replace("_dtm.tif", "_dtm_3x3_merge_horangle")

        """
        Prepare command
        """
        #reference to year 2022
        procs = ()
        out_raster_name = []
        rSun_day = 0
        for month_num in range(1, 13):
            num_days = monthrange(2022, month_num)[1]
            datetime_object = datetime.datetime.strptime(str(month_num), "%m")
            month = (datetime_object.strftime("%B")).lower()
            
            for day in range(1, num_days+1):
                rSun_day = rSun_day + 1
                rSun_raster = rSun_baseName + month + "_" + str(day)
                out_raster_name.append(rSun_raster)
                procs += ([dtm_raster, horizon_baseName, horizon_step, aspect_raster, slope_raster, month, rSun_day, rSun_raster,],)
            
        with Pool(MAX_PROCESSOR) as p:
            p.map(process_data, procs)
        
        """
        Export rSun raster
        """
        outFolder_rSun = os.path.join( outFolder, f.replace("_dtm.tif", "") )
        os.mkdir(outFolder_rSun)
        for raster in out_raster_name:
            export_rSun_map(raster, outFolder_rSun)
            raster_list = raster_list + "," + raster
        
        """
        Remove all raster and vector
        """
        remove_raster(raster_list, prjPath)
        remove_vector(tile_vector, prjPath)


###################################################################
# Main function
#
###################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--dataFolder', help='input dataFolder')
    parser.add_argument('--outFolder', help='output dataFolder')
    parser.add_argument('--horizon_step', help='horizon_step value')

    args = parser.parse_args()
    """
    Get Start Time
    """
    start_time_main = timeit.default_timer()

    dataFolder = args.dataFolder
    outFolder = args.outFolder
    horizon_step = args.horizon_step

    horizon_start = 0
    horizon_end = 360

    """
    Modify these variables according to your project
    """
    coord_system_code = 7791
    location_name = "/home/FerraraLocation"
    linkeFolder = "/root/PV_ferrara/FE_data/linkeMap/linkeMap_7791"

    """
    Set project path
    """
    base_location = os.path.join("home", location_name)

    """
    Create new project Location
    """
    prjPath = create_project(coord_system_code, base_location)

    """
    Import linke raster map
    """
    for r in os.listdir(linkeFolder):
        if (".xml" not in r):
            monthName = r.split("_cut_scaled")[0]
            import_raster(os.path.join(linkeFolder, r), monthName + ".tif", prjPath)

    """
    Create outputFolder
    """
    outFolder = check_outfolder(dataFolder)

    """
    Get list of Horizon map
    """
    horizon_list = os.listdir(os.path.join(dataFolder, "horizon"))

    """
    Compute r.sun for each tile
    """
    dataList = os.listdir(os.path.join(dataFolder, "tile"))
    for f in dataList:
        if (".shp" in f):
            dtm_name = f.replace("_tile.shp", "_dtm.tif")
            prepare_data(dtm_name, prjPath, dataFolder, horizon_list, horizon_step, outFolder)

    """
    Get Elapsed Time
    """
    elapsed_time = timeit.default_timer() - start_time_main
    print ("---> Time elapsed r.sun: " + time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))