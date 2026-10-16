import os, shutil
import subprocess, shlex
from subprocess import Popen, PIPE
from calendar import monthrange
import datetime
from multiprocessing import Process, Pool
import multiprocessing as mp
import timeit
import time, sys


MAX_PROCESSOR = mp.cpu_count() - 2


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
# This function import vector
#
###################################################################
def import_vector(inFile, outName, prjPath):
    cmd = "grass " + prjPath + " --exec v.import --overwrite input=" + inFile + " output=" + outName

    run_grass_cmd(cmd)

    return outName


###################################################################
# This function import raster
#
###################################################################
def import_raster(inFile, outName, prjPath):
    if ( os.path.exists(inFile) ):
        cmd = "grass " + prjPath + " --exec r.import --overwrite input=" + inFile + " output=" + outName

        run_grass_cmd(cmd)

        return outName
    else:
        return None

###################################################################
# This function set grass region
#
###################################################################
def set_region(raster_name, res, prjPath, region_type):
    cmd = "grass " + prjPath + " --exec g.region " + region_type + "=" + raster_name + " res=" + str(res)

    run_grass_cmd(cmd)


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
# This function merge input raster
#
###################################################################
def merge_raster(list_rasterName, prjPath, outName):
    cmd = "grass " + prjPath + " -f --exec r.patch input=" + list_rasterName + " output=" + outName

    run_grass_cmd(cmd)

    return outName


###################################################################
# This function export 3x3 maps
#
###################################################################
def export_raster_map(raster_name, prjPath, outFolder):
    cmd = "grass " + prjPath + " -f --exec r.null map=" + str(raster_name) + " null=0"

    run_grass_cmd(cmd)


    cmd_1 = "grass " + prjPath + " -f --exec r.out.gdal -f input=" + str(raster_name) + " output=" + os.path.join(outFolder, "mosaic_month", raster_name + ".tif") + " format=GTiff"

    run_grass_cmd(cmd_1)


###################################################################
# This function create folder to save all output
#
###################################################################
def check_outfolder(dataFolder):
    outFolder = os.path.join(dataFolder, "mosaic_month")

    if (os.path.isdir(outFolder)):
        shutil.rmtree(outFolder)
    
    os.mkdir(outFolder)


###################################################################
# This function create folder remove input raster
#
###################################################################
def remove_raster(list_rasterName, prjPath):
    cmd = "grass " + prjPath + " -f --exec g.remove -f type=raster name=" + list_rasterName

    run_grass_cmd(cmd)


def process_data(prjPath, month, dataFolder):

    path = os.path.join(dataFolder, "rSun_sum")
    #
    print('#>>>>>>>>>>>>  ', month)
    #list of all files in rSun_sum containing the month
    month_list= []
    for root, dirs, files in os.walk(path):
	    for file in files:
		    if(file.endswith(month)):
			    month_list.append(os.path.join(root,file))


    """
    Import all raster with same month
    """
    rasterName_arr = []
    for iter, n_id in enumerate(month_list):
        rasterName = n_id.split("rSun_sum/",1)[1]
        rasterName_arr.append( import_raster( os.path.join(dataFolder, "rSun_sum", rasterName), rasterName.split("/",1)[1], prjPath ) )
    



    list_rasterName = ",".join(r for r in rasterName_arr if r is not None)  # FIX: no leading comma
    """
    Set region
    """
    set_region(list_rasterName, 1, prjPath, "raster")
    
    """
    Merge all dtm
    """   
    raster_name = merge_raster(list_rasterName, prjPath, f"{month}_mosaic")

    """
    Export raster map
    """
    export_raster_map(raster_name, prjPath, dataFolder)

    """
    Delete all rester
    """
    list_rasterName = list_rasterName + "," + str(raster_name)
    remove_raster(list_rasterName, prjPath)


###################################################################
# Main function
#
###################################################################
if __name__ == "__main__":
    coord_system_code = 7791
    location_name = "/home/FerraraLocation"

    """
    Get Start Time
    """
    start_time_main = timeit.default_timer()

    """
    Set name of first and last dtm to be processed
    """
    # first_dtm = "5h691551305_DSMFirst_dtm"
    # last_dtm = "5h691551340_DSMFirst_dtm"

    """
    Set input data folder
    """
    # dataFolder = "/root/data/input/qgis/2/output"
    dataFolder = "/root/PV_ferrara/FE_data/output"

    """
    Set project path
    """
    base_location = os.path.join("home", location_name)

    """
    Create new project Location
    """
    prjPath = create_project(coord_system_code, base_location)

    """
    Check outFolder
    """
    check_outfolder(dataFolder)

    # start_process = False
    for month in ['january','february','march','april','may','june','july','august','september','october','november','december','year']:  # FIX: also mosaic the yearly sum
        process_data(prjPath, month, dataFolder)

    """
    Get Elapsed Time
    """
    elapsed_time = timeit.default_timer() - start_time_main
    print ("---> Time elapsed mosaic: " + time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))


        


        
    

