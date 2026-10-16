import os, shutil
import subprocess, shlex
from subprocess import Popen, PIPE
from calendar import monthrange
import datetime
import timeit
import time
import sys
import argparse
import json

MAX_DATASET_PART = 8


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
# This function export raster map
#
###################################################################
def export_raster_map(raster_name, outFolder):
    cmd = "grass " + prjPath + " -f --exec r.out.gdal input=" + raster_name + " output=" + os.path.join(outFolder, raster_name) + " format=GTiff"

    run_grass_cmd(cmd)


###################################################################
# compute r.series grass
#
###################################################################
def compute_rSeries(list_raster, outName, prjPath):
    cmd = "grass " + prjPath + " -f --exec r.series --overwrite input=" + list_raster + " output=" + outName + " method=sum"

    run_grass_cmd(cmd)


###################################################################
# This function create folder to save all output
#
###################################################################
def create_outDataFolder(outFolder, folderName):
    outDataFolder = os.path.join(outFolder, folderName)

    if (os.path.isdir(outDataFolder)):
        shutil.rmtree(outDataFolder)
    
    os.mkdir(outDataFolder)

    return outDataFolder


###################################################################
# Split dataset
#
###################################################################
def split(a, n):
	k, m = divmod(len(a), n)
	return (a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))


###################################################################
# Process data for rSun month
#
###################################################################
def process_data_rSun_month(dataset, prjPath, dataFolder, outFolder):
    for raster_name in dataset:
        vector_list = []
        """
        Create folder to save result data
        """
        outDataFolder = create_outDataFolder(outFolder, raster_name)

        """
        Import vector tile
        """
        tile_path = os.path.join(dataFolder, "tile", raster_name + "_tile.shp")
        tile_vector = import_vector(tile_path, "tile", prjPath)
        vector_list.append(tile_vector)

        """
        Set region
        """
        set_region(tile_vector, 1, prjPath, "vector")

        """
        Set folder to get rSun raster and get all files
        """
        rSun_folder = os.path.join(dataFolder, "rSun", raster_name)
        rSun_files = os.listdir(rSun_folder)

        """
        Get all raster by month and merge them
        """
        for month_num in range(1, 13):
            num_days = monthrange(2022, month_num)[1]
            datetime_object = datetime.datetime.strptime(str(month_num), "%m")
            month = (datetime_object.strftime("%B")).lower()

            month_files = [s for s in rSun_files if ("_" + month + "_") in s and not s.endswith(".aux.xml")]  # FIX: skip sidecar files

            """
            Import rSun raster maps
            """
            rSun_raster_list = []
            for rSun_raster_name in month_files:
                rSun_raster_list.append( import_raster(os.path.join(rSun_folder, rSun_raster_name), rSun_raster_name, prjPath) )
            
            """
            Compute r.series
            """
            outName = raster_name + "_" + month
            list_raster = ",".join(rSun_raster_list)
            compute_rSeries(list_raster, outName, prjPath)

            """
            Export result raster
            """
            export_raster_map(outName, outDataFolder)
            rSun_raster_list.append(outName)
            list_raster = ",".join(rSun_raster_list)

            """
            Remove raster
            """
            remove_raster(list_raster, prjPath)
        
        """
        Remove vector
        """
        listVector = ",".join(vector_list)
        remove_vector(listVector, prjPath)


###################################################################
# Process data for rSun year
#
###################################################################
def process_data_rSun_year(dataset, prjPath, dataFolder, outFolder):
    for raster_name in dataset:
        vector_list = []
        """
        Import vector tile
        """
        tile_path = os.path.join(dataFolder, "tile", raster_name + "_tile.shp")
        tile_vector = import_vector(tile_path, "tile", prjPath)
        vector_list.append(tile_vector)

        """
        Set region
        """
        set_region(tile_vector, 1, prjPath, "vector")

        """
        Set folder to get rSun raster and get all files
        """
        rSun_month_folder = os.path.join(outFolder, raster_name)
        rSun_month_files = [s for s in os.listdir(rSun_month_folder) if not s.endswith("_year") and not s.endswith(".aux.xml")]  # FIX: avoid double counting on rerun

        rSun_month_raster_list = []

        """
        Merge all raster by year
        """
        for raster in rSun_month_files:
            """
            Import rSun raster maps
            """
            rSun_month_raster_list.append( import_raster(os.path.join(rSun_month_folder, raster), raster, prjPath) )

        """
        Compute r.series
        """
        outName = raster_name + "_year"
        list_raster = ",".join(rSun_month_raster_list)
        compute_rSeries(list_raster, outName, prjPath)

        """
        Export result raster
        """
        export_raster_map(outName, os.path.join(outFolder, raster_name))
        rSun_month_raster_list.append(outName)
        list_raster = ",".join(rSun_month_raster_list)

        """
        Remove raster
        """
        remove_raster(list_raster, prjPath)
    
    """
    Remove vector
    """
    listVector = ",".join(vector_list)
    remove_vector(listVector, prjPath)


###################################################################
# Main function
#
###################################################################
if __name__ == "__main__":
    """
    Do not modify this variable
    """
    location_name = "/home/FerraraLocation"
    coord_system_code = 7791

    parser = argparse.ArgumentParser(description='Group rsun by month and year.')
    parser.add_argument('--dataFolder', help='input dataFolder')
    parser.add_argument('--outFolder', help='output dataFolder')                    # manually create out folder called "rSun_sum"
    parser.add_argument('--process', help='process type [rsun_month / rsun_year]')  # key sensitive
    parser.add_argument('--dataset_nr', help='dataset number - the dataset is divided into n parts according to the parameter "MAX_DATASET_PART". To control which division to process, use the parameter "dataset_nr". For example, if I want to process the first part I would set the parameter "dataset_nr" = 0')

    args = parser.parse_args()

    """
    Get Start Time
    """
    start_time_main = timeit.default_timer()

    dataFolder = args.dataFolder
    outFolder = args.outFolder
    process = args.process
    dataset_nr = int(args.dataset_nr)

    """
    Create new project Location
    """
    prjPath = create_project(coord_system_code, location_name)

    if ("rsun_month" in process):
        """
        Get path of the folder to be processed
        """
        inFolder = os.path.join(dataFolder, "rSun")

        """
        Get all file inside inFolder
        """
        files = os.listdir(inFolder)

        """
        Split dataset in n part
        """
        # split_files = list( split(files, MAX_DATASET_PART) )            # view line 128 for more info

        """
        Process specific part of dataset
        """
        if (dataset_nr >= MAX_DATASET_PART):
            print ("Error dataset_nr is not correct. Max number of part = " + str(MAX_DATASET_PART))
        else:
            # process_data_rSun_month(split_files[dataset_nr], prjPath, dataFolder, outFolder)
            process_data_rSun_month(files, prjPath, dataFolder, outFolder)


    elif ("rsun_year" in process):
        """
        Get path of the folder to be processed
        """
        inFolder = os.path.join(dataFolder, "rSun_sum")

        """
        Get all file inside inFolder
        """
        files = os.listdir(inFolder)

        """
        Split dataset in n part
        """
        # split_files = list( split(files, MAX_DATASET_PART) )

        """
        Process specific part of dataset
        """
        if (dataset_nr >= MAX_DATASET_PART):
            print ("Error dataset_nr is not correct. Max number of part = " + str(MAX_DATASET_PART))
        else:
            # process_data_rSun_year(split_files[dataset_nr], prjPath, dataFolder, outFolder)
            process_data_rSun_year(files, prjPath, dataFolder, outFolder)

    
    else:
        print ("Error, process doesn't exist. Use 'rsun_month' or 'rsun_year'")

    """
    Get Elapsed Time
    """
    elapsed_time = timeit.default_timer() - start_time_main
    print ("---> Time elapsed r.sun: " + time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))