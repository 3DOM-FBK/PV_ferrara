# Solar radiation estimantion pipeline

## run on docker
1) create image by:
```
docker load --input grassv2.tar
```
2) create container
```
docker run -it -v /home/beber/fbk_sandbox/PV-ferrara/data/PV_ferrara/:/root/PV_ferrara/ grass_v2:v78 bash
```
3) run scripts from within `/root/PV_ferrara` folder
4) run `processQGISData.py` script from qgis Python Console settin gproper folder
5) `mkdir ../FE_data/output/3x3_tile`
6) run `generate_3x3Tile.py` script from within the docker image `grass_v2   v78   5153b58fdd12  `
7) create linkeMap for AOI >> https://www.soda-pro.com/help/general-knowledge/linke-turbidity-factor
  explanation: https://atmosphere.copernicus.eu/sites/default/files/2019-01/CAMS72_2015SC3_D72.1.3.1_2018_UserGuide_v1_201812.pdf
7) WARP create your own LINKE map

8) run `. 0_warp_and_crop.sh` once repjected, need to crop to AOI
```
find ./LINKE -type f -name "*.tif" -printf "gdalwarp -overwrite -s_srs EPSG:4326 -t_srs EPSG:32632 -r cubic -of GTiff -srcnodata \"n/a\" -dstnodata NoData -cutline ../Italy_FE/italy_FE_area.shp %p ./re_prj/rprj_%f \n" > 0_warp_and_crop.sh
```
9) run `. 1_warp_and_Nocrop_FE.sh`
```
find ./re_prj -type f -name "*.tif" -printf "gdalwarp -overwrite -s_srs epsg:32632 -t_srs epsg:32632 -of GTiff -srcnodata \"n/a\" -dstnodata NoData -tr 500 500 -r cubic %p ./cut/cut_%f \n" > 1_warp_and_Nocrop_FE.sh
```
10) run `. 2_crop_FE.sh`
```
find ./cut -type f -name "*.tif" -printf "gdalwarp -overwrite -s_srs epsg:32632 -t_srs epsg:32632 -of GTiff -srcnodata \"n/a\" -dstnodata NoData -cutline ../Ferrara_AOI/Ferrara_AOI_UTM32N_WGS84.shp -crop_to_cutline %p ./crop_FE/cFE_%f \n" > 2_crop_FE.sh
```
11) run `. 3_scales.sh`

```
find ./crop_FE -type f -name "*.tif" -printf "gdal_calc.py -A ./crop_FE/%f --outfile=./scaled/sca_%f --calc="A/20" --overwrite --type=Float32 \n" > 3_scales.sh  
```

12) `cp -r scaled linkeMap`
13) `cd linkeMap/`
14) `rename 's/sca_cFE_cut_rprj_TL2010_//' *.tif`
15) `rename 's/_gf/_cut_scaled/' *.tif`
16) run `python3 generateHorizonGrass.py`
17) run
```
python3 generateRsunParallel.py --dataFolder /root/PV_ferrara/test_data/output --outFolder /root/PV_ferrara/test_data/output/rSun --horizon_step 10

```
18) `mkdir rSun_sum`
19) run
```|
python3 generate_Rsun_MonthMaps.py --dataFolder /root/PV_ferrara/test_data/output --outFolder /root/PV_ferrara/test_data/output/rSun_sum --process rsun_month --dataset_nr 0
```


## UTILS:
delete xml files

```
find . -name "*.xml" -type f|xargs rm -f
```

## TODOS:
1) integrate border DTM with coarser res EU-DEM
2) solve issue with xml file produced by QGIS script
