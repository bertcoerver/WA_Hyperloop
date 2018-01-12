# -*- coding: utf-8 -*-
"""
Created on Fri Oct 13 13:28:17 2017

@author: bec
"""
import os
import WA_Hyperloop.becgis as becgis
from WA_Hyperloop.sheet5_functions import sheet5_functions as sh5
from WA_Hyperloop.sheet2_functions import sheet2_functions as sh2
from WA_Hyperloop.sheet3_functions import sheet3_functions as sh3
import WA_Hyperloop.get_dictionaries as gd
import glob
import davgis
import netCDF4
import wa.Generator.Sheet5.main as Sheet5
from shutil import copyfile
from WA_Hyperloop.sheet1_functions import sheet1_functions as sh1
import matplotlib.pyplot as plt
import numpy as np
import WA_Hyperloop.pairwise_validation as pwv
import ogr
import wa.General.raster_conversions as RC
import subprocess
import wa.General.data_conversions as LA
import shutil

def diagnosis_wp(metadata, complete_data, output_dir, waterpix):

    output_dir = os.path.join(output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
   
    LU = becgis.OpenAsArray(metadata['lu'], nan_values = True)
    
#    S = SortWaterPix(waterpix, 'Supply_M', output_dir)
#    becgis.MatchProjResNDV(metadata['lu'], becgis.ListFilesInFolder(S), os.path.join(output_dir, "s_matched"))
#    complete_data['supply'] = becgis.SortFiles(os.path.join(output_dir, "s_matched"), [-10,-6], month_position = [-6,-4])[0:2]
    
    common_dates = becgis.CommonDates([complete_data['p'][1],complete_data['et'][1],complete_data['tr'][1], complete_data['etb'][1]])
    
    becgis.AssertProjResNDV([complete_data['p'][0],complete_data['et'][0],complete_data['tr'][0]])
    
    balance_km3 = np.array([])
    
    p_km3 = np.array([])
    et_km3 = np.array([])
    ro_km3 = np.array([])

    balance_mm = np.array([])
    
    p_mm = np.array([])
    et_mm = np.array([])
    ro_mm = np.array([])    

    area = becgis.MapPixelAreakm(metadata['lu'])
    
    for date in common_dates:
        
        print date
        
        P = complete_data['p'][0][complete_data['p'][1] == date][0]
        ET = complete_data['et'][0][complete_data['et'][1] == date][0]
        RO = complete_data['tr'][0][complete_data['tr'][1] == date][0]
        
        factor = 0.001 * 0.001 * area
        
        p = becgis.OpenAsArray(P, nan_values = True)
        et = becgis.OpenAsArray(ET, nan_values = True) 
        ro = becgis.OpenAsArray(RO, nan_values = True)
    
        p[np.isnan(LU)] = et[np.isnan(LU)] = ro[np.isnan(LU)] = np.nan
    
        balance_km3 = np.append(balance_km3, np.nansum(p * factor) - np.nansum(et * factor) - np.nansum(ro * factor))
        p_km3 = np.append(p_km3, np.nansum(p * factor))
        et_km3 = np.append(et_km3, np.nansum(et * factor))
        ro_km3 = np.append(ro_km3, np.nansum(ro * factor))
        
        balance_mm = np.append(balance_mm, np.nanmean(p) - np.nanmean(et) - np.nanmean(ro))
        p_mm = np.append(p_mm, np.nanmean(p))
        et_mm = np.append(et_mm, np.nanmean(et))
        ro_mm = np.append(ro_mm, np.nanmean(ro))
   
    relative_storage = np.cumsum(balance_km3) / np.mean(p_km3)
    
    ##
    # BASIC BASINSCALE WATERBALANCE (PRE-SHEETS)
    ##
    fig = plt.figure(1, figsize = (9,6))
    plt.clf()
    fig.patch.set_alpha(0.7)
    
    ax2 = plt.gca()
    ax = ax2.twinx()
    
    ax2.bar(common_dates, relative_storage, width = 25, color = '#3ee871')
    
    ax2.grid(b=True, which='Major', color='0.65',linestyle='--', zorder = 0)
    ax.bar([common_dates[0]],[0], label = '$\sum dS / \overline{P}$', color = '#3ee871')
    ax.plot(common_dates, np.cumsum(balance_km3), label = '$\sum dS$')
    ax.plot(common_dates, np.cumsum(p_km3), label = '$\sum (P)$')
    ax.plot(common_dates, np.cumsum(et_km3) + np.cumsum(ro_km3), label = '$\sum (ET + RO)$')

    box = ax.get_position()
    ax.set_position([box.x0, box.y0 + box.height * 0.1,
                 box.width, box.height * 0.9])
    ax2.set_position([box.x0, box.y0 + box.height * 0.1,
                 box.width, box.height * 0.9])

    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1),
          fancybox=True, shadow=True, ncol=5)

    plt.suptitle('$\sum P = {0:.1f}\;{4}, \\ \sum ET = {1:.1f}\;{4}, \sum RO = {2:.1f}\;{4}, \sum dS = {3:.1f}\;{4}$'.format(np.sum(p_km3), np.sum(et_km3), np.sum(ro_km3), np.sum(balance_km3), r"km^{3}"))
    plt.title('{0}, ${5} = {2:.3f}\;{6}, {7} = {3:.3f}, dt = {4}\;months$'.format(metadata['name'], np.sum(balance_km3), np.mean(balance_km3), np.mean(relative_storage), len(p_km3), r"\overline{dS}", r"km^{3}", r"\overline{\sum dS / \overline{P}}"))
    plt.xlabel('Time')
    
    ax2.set_ylabel('Relative Storage [months of $\overline{P}$]')
    ax.set_ylabel('Stock [$km^{3}$]')
    #plt.savefig(os.path.join(output_dir, 'balance_{0}'.format(metadata['name'])))

    fig = plt.figure(2)
    plt.clf()
    
    ax2 = plt.gca()
    ax = ax2.twinx()
    
    ax2.plot(common_dates, p_mm, common_dates, et_mm, common_dates, ro_mm)
    ax.plot(common_dates, np.cumsum(balance_mm), 'k')
    

def diagnosis(metadata, complete_data, output_dir, all_results, waterpix):

    output_dir = os.path.join(output_dir, metadata['name'], "diagnosis")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    S = SortWaterPix(waterpix, 'Supply_M', output_dir)
    becgis.MatchProjResNDV(metadata['lu'], becgis.ListFilesInFolder(S), os.path.join(output_dir, "s_matched"))
    complete_data['supply'] = becgis.SortFiles(os.path.join(output_dir, "s_matched"), [-10,-6], month_position = [-6,-4])[0:2]
    
    LU = becgis.OpenAsArray(metadata['lu'], nan_values = True)
    
    common_dates = becgis.CommonDates([complete_data['p'][1],complete_data['et'][1],complete_data['tr'][1], complete_data['etb'][1]])
    
    becgis.AssertProjResNDV([complete_data['p'][0],complete_data['et'][0],complete_data['tr'][0]])
    
    balance = np.array([])
    balance2 = np.array([])
    
    p_y = np.array([])
    et_y = np.array([])
    ro_y = np.array([])
    bf_y = np.array([])
    supply_y = np.array([])
    
    ds_y = np.array([])
    
    area = becgis.MapPixelAreakm(metadata['lu'])
    
    for date in common_dates:
        
        P = complete_data['p'][0][complete_data['p'][1] == date][0]
        ET = complete_data['et'][0][complete_data['et'][1] == date][0]
        RO = complete_data['tr'][0][complete_data['tr'][1] == date][0]
        BF = complete_data['bf'][0][complete_data['bf'][1] == date][0]
        DS = complete_data['ds'][0][complete_data['ds'][1] == date][0]
        supply = complete_data['supply'][0][complete_data['supply'][1] == date][0]
        
        p = becgis.OpenAsArray(P, nan_values = True) * 0.001 * 0.001 * area
        et = becgis.OpenAsArray(ET, nan_values = True) * 0.001 * 0.001 * area
        ro = becgis.OpenAsArray(RO, nan_values = True) * 0.001 * 0.001 * area
        bf = becgis.OpenAsArray(BF, nan_values = True) * 0.001 * 0.001 * area
        ds = becgis.OpenAsArray(DS, nan_values = True) * 0.001 * 0.001 * area
        supply = becgis.OpenAsArray(supply, nan_values = True) * 0.001 * 0.001 * area
    
        p[np.isnan(LU)] = et[np.isnan(LU)] = ro[np.isnan(LU)] = bf[np.isnan(LU)] = ds[np.isnan(LU)] = supply[np.isnan(LU)] =  np.nan
    
        balance = np.append(balance, np.nansum(p) - np.nansum(et) - np.nansum(ro))
        balance2 = np.append(balance2, np.nansum(p) + np.nansum(supply) - np.nansum(et) - np.nansum(ro) - np.nansum(bf))
        
        p_y = np.append(p_y, np.nansum(p))
        et_y = np.append(et_y, np.nansum(et))
        ro_y = np.append(ro_y, np.nansum(ro))
        bf_y = np.append(bf_y, np.nansum(bf))
        ds_y = np.append(ds_y, np.nansum(ds))
        supply_y = np.append(supply_y, np.nansum(supply))
    
    ###
    # CHECK ET
    ###
    plt.figure(2)
    plt.clf()
    et = sh1.get_ts(all_results, 'et_advection') + sh1.get_ts(all_results, 'p_recycled')
    plt.scatter(et_y, et)
    plt.xlabel('ETens [km3/month]')
    plt.ylabel('Sheet1 [km3/month]')
    nash = pwv.nash_sutcliffe(et_y, et)
    plt.title('EVAPO, NS = {0}'.format(nash))
    plt.savefig(os.path.join(output_dir, "CHECK_ET.jpg"))
    
    ##
    #CHECK P
    ##
    plt.figure(3)
    plt.clf()
    p = sh1.get_ts(all_results, 'p_advection') + sh1.get_ts(all_results, 'p_recycled')
    plt.scatter(p_y, p)
    plt.xlabel('CHIRPS [km3/month]')
    plt.ylabel('Sheet1 [km3/month]')
    nash = pwv.nash_sutcliffe(p_y, p)
    plt.title('PRECIPITATION, NS = {0}'.format(nash))
    plt.savefig(os.path.join(output_dir, "CHECK_P.jpg"))
    
    ##
    # CHECK Q
    ##
    #correction = calc_missing_runoff_fractions(metadata)['full']
    plt.figure(4)
    plt.clf()
    q = sh1.get_ts(all_results, 'q_out_sw') -  sh1.get_ts(all_results, 'q_in_sw')  +  sh1.get_ts(all_results, 'q_out_gw')  -  sh1.get_ts(all_results, 'q_in_gw') +  sh1.get_ts(all_results, 'q_outflow') - sh1.get_ts(all_results, 'q_in_desal')
    plt.scatter(ro_y, q, label = 'original')
    #plt.scatter(ro_y * correction, q, label = 'corrected')
    plt.legend()
    plt.xlabel('Waterpix_runoff [km3/month]')
    plt.ylabel('Sheet1 [km3/month]')
    nash = pwv.nash_sutcliffe(ro_y, q)
    #nash2 = pwv.nash_sutcliffe(ro_y * correction, q)
    plt.title('RUNOFF, NS = {0}'.format(nash))
    plt.savefig(os.path.join(output_dir, "CHECK_Q.jpg"))  
    
    ###
    # CHECK dS
    ###
    plt.figure(5)
    plt.clf()
    ds = sh1.get_ts(all_results, 'dS')
    plt.scatter(balance, ds * -1)
    plt.xlabel('CHIRPS, ETens, WPrunoff [km3/month]')
    plt.ylabel('Sheet1')
    nash = pwv.nash_sutcliffe(balance, ds * -1)
    plt.title('dS, NS = {0}'.format(nash))
    plt.savefig(os.path.join(output_dir, "CHECK_dS.jpg"))
    
    ###
    # CHECK WATERBALANCE (POST-SHEET1)
    ###
    balance_sheet1 = p - et - q
    plt.figure(6)
    plt.clf()
    
    plt.plot(common_dates, np.cumsum(balance), label = 'dS [CHIRPS, ETens, WPro]')
    plt.plot(common_dates, np.cumsum(balance_sheet1), label = 'dS [P(sh1), ET(sh1) + Q(sh1)]')
    plt.plot(common_dates, np.cumsum(ds) * -1, label = 'dS [sh1]')
    
    plt.plot(common_dates, np.cumsum(p_y), label = 'CHIRPS')
    plt.plot(common_dates, np.cumsum(p), label = 'P [sh1]')
    
    plt.plot(common_dates, np.cumsum(et_y) + np.cumsum(ro_y), label = 'ETens + WPro')
    plt.plot(common_dates, np.cumsum(et) + np.cumsum(q), label = 'ET [sh1] + Q [sh1]')
    
    plt.legend()
    plt.xlabel('Months')
    plt.ylabel('Flux [km3/month]')
    plt.savefig(os.path.join(output_dir, "CHECK_WB.jpg"))
    
def prepareSurfWatLoop(data, global_data):

    data_needed = ["etref_folder", "et_folder", "p_folder"]

    data_dst = {"etref_folder": r"ETref\Monthly",
                "et_folder":    r"Evaporation\ETensV1_0",
                "p_folder":     r"Precipitation\CHIRPS\Monthly"}

    for data_name in data_needed:
        print data_name
        files, dates = becgis.SortFiles(data[data_name], [-10, -6],
                                        month_position=[-6, -4])[0:2]

        for f, d in zip(files, dates):

            fp = os.path.split(f)[1]

            dst = os.path.join(os.environ["WA_HOME"],
                               'Loop_SW', data_dst[data_name],
                               fp[:-4] +
                               "_monthly_{0}.{1}.01.tif".format(d.year,
                                                                str(d.month).zfill(2)))

            folder = os.path.split(dst)[0]

            if not os.path.exists(folder):
                os.makedirs(folder)

            copyfile(f, dst)

    pt = os.path.join(os.environ["WA_HOME"], 'Loop_SW', 'HydroSHED', 'DIR')

    if not os.path.exists(pt):
        os.makedirs(pt)

    copyfile(global_data['dir'], os.path.join(pt, "DIR_HydroShed_-_15s.tif"))

def LoopSurfWat(waterpix, metadata, global_data, big_basins = None):

    dst = os.path.join(os.environ["WA_HOME"], "LU", "Loop_SW.tif")
    if os.path.exists(dst):
        os.remove(dst)

    copyfile(metadata['full_basin_mask'], dst)

    Basin = 'Loop_SW'

    P_Product = 'CHIRPS'
    ET_Product = 'ETensV1_0'
    Inflow_Text_Files = []
    Reservoirs_GEE_on_off = 0
    Supply_method = "Fraction"
    ID = metadata['id']

    pt = os.path.join(os.environ["WA_HOME"], 'Loop_SW', 'HydroSHED', 'DEM')
    pt2 = os.path.join(os.environ["WA_HOME"], 'Loop_SW', 'HydroSHED', 'DIR')

    if os.path.exists(os.path.join(pt, "DEM_HydroShed_m_15s.tif")):
        os.remove(os.path.join(pt, "DEM_HydroShed_m_15s.tif"))
    if os.path.exists(os.path.join(pt2, "DIR_HydroShed_-_15s.tif")):
        os.remove(os.path.join(pt2, "DIR_HydroShed_-_15s.tif"))

    start = str(netCDF4.Dataset(waterpix).variables["time_yyyymm"][:][0])
    end = str(netCDF4.Dataset(waterpix).variables["time_yyyymm"][:][-1])
    
    Startdate = "{0}-{1}-01".format(start[0:4], start[4:6])
    Enddate = "{0}-{1}-31".format(end[0:4], end[4:6])
    
    print Startdate, Enddate
    
    if ID in big_basins:
        
        surfwater_path = list()
        
        years = range(int(Startdate[0:4]), int(Enddate[0:4])+1)
        
        ID = ID * 100
        
        for year in years:
            
            ID += 1
            Startdate = "{0}-01-01".format(year)
            Enddate = "{0}-12-31".format(year)          
            
            filename = os.path.join(os.environ["WA_HOME"], "Loop_SW", "Simulations", "Simulation_{0}".format(ID), "Sheet_5", "Discharge_CR1_Simulation{0}_monthly_m3_01{1}_12{1}.nc".format(ID, int(year)))
            
            if not os.path.exists(filename):
                Sheet5.Calculate(Basin, 
                                 P_Product, 
                                 ET_Product, 
                                 Inflow_Text_Files, 
                                 waterpix, 
                                 Reservoirs_GEE_on_off, 
                                 Supply_method, 
                                 Startdate, 
                                 Enddate, 
                                 ID)
                os.remove(os.path.join(pt, "DEM_HydroShed_m_15s.tif"))
                os.remove(os.path.join(pt2, "DIR_HydroShed_-_15s.tif"))
       
            else:
                pass
            
            surfwater_path.append(filename)

    else:

        surfwater_path = os.path.join(os.environ["WA_HOME"], "Loop_SW", "Simulations", "Simulation_{0}".format(ID), "Sheet_5", "Discharge_CR1_Simulation{0}_monthly_m3_012003_122014.nc".format(ID))
 
        if not os.path.exists(surfwater_path):   
            Sheet5.Calculate(Basin, 
                             P_Product, 
                             ET_Product, 
                             Inflow_Text_Files, 
                             waterpix, 
                             Reservoirs_GEE_on_off, 
                             Supply_method, 
                             Startdate, 
                             Enddate, 
                             ID)
            os.remove(os.path.join(pt, "DEM_HydroShed_m_15s.tif"))
            os.remove(os.path.join(pt2, "DIR_HydroShed_-_15s.tif"))
        else:
            pass
        

    return surfwater_path
    
def sort_data_short(output_dir, metadata):
    data = ['p', 'et', 'n', 'ndm', 'lai', 'etref', 'etb', 'etg', 'i', 't', 'r', 'bf', 'sr', 'tr', 'perc', 'dperc']
    complete_data = dict()
    for datatype in data:
        try:
            folder = os.path.join(output_dir, metadata['name'], datatype)
            for fn in glob.glob(folder + "\\*_km3.tif"):
                os.remove(fn)
            files, dates = becgis.SortFiles(folder, [-10,-6], month_position = [-6,-4])[0:2]
            complete_data[datatype] = (files, dates)
        except: 
            print datatype
            continue
#    data_2 = ['SUPPLYsw','RETURNFLOW_gwsw','RETURNFLOW_swsw',r'fractions\fractions']
    
    data_2dict = {'SUPPLYsw': 'supply_sw',
                  'RETURNFLOW_gwsw': 'return_flow_gw_sw',
                  'RETURNFLOW_swsw': 'return_flow_sw_sw',
                  r'fractions\fractions': 'fractions'
                  }

    for datatype in data_2dict.keys():
        try:
            folder = os.path.join(output_dir, metadata['name'], datatype)
            for fn in glob.glob(folder + "\\*_km3.tif"):
                os.remove(fn) 
            files, dates = becgis.SortFiles(folder, [-11,-7], month_position = [-6,-4])[0:2]
            complete_data[data_2dict[datatype]] = (files, dates)
        except: 
            print datatype
            continue
    
    return complete_data

def sort_data(data, metadata, global_data, output_dir):
    output_dir = os.path.join(output_dir, metadata['name'])
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    complete_data = dict()
    for key in data.keys():
        complete_data = sort_var(data, metadata, global_data, output_dir, key, complete_data)

    complete_data['fractions'] = sh5.calc_fractions(complete_data['p'][0], complete_data['p'][1], os.path.join(output_dir, 'fractions'), global_data['dem'], metadata['lu'])

    i_files, i_dates, t_files, t_dates = sh2.splitET_ITE(complete_data['et'][0], complete_data['et'][1], complete_data['lai'][0], complete_data['lai'][1], complete_data['p'][0], complete_data['p'][1], complete_data['n'][0], complete_data['n'][1], complete_data['ndm'][0], complete_data['ndm'][1], output_dir, ndm_max_original = False, plot_graph = True, save_e = False)

    complete_data['i'] = (i_files, i_dates)
    complete_data['t'] = (t_files, t_dates)
    
    gb_cats, mvg_avg_len = gd.get_bluegreen_classes(version = '1.0')
    etblue_files, etblue_dates, etgreen_files, etgreen_dates = sh3.splitET_BlueGreen(complete_data['et'][0], complete_data['et'][1], complete_data['etref'][0], complete_data['etref'][1], complete_data['p'][0], complete_data['p'][1], metadata['lu'], output_dir, 
                  moving_avg_length = mvg_avg_len, green_blue_categories = gb_cats, plot_graph = False, 
                  method = 'tail', scale = 1.1, basin = metadata['name'])
                      
    complete_data['etb'] = (etblue_files, etblue_dates)
    complete_data['etg'] = (etgreen_files, etgreen_dates)
    
    return complete_data


def sort_var(data, metadata, global_data, output_dir, key, complete_data):
    files, dates = becgis.SortFiles(data[key], [-10,-6], month_position = [-6,-4])[0:2]
    scales = {'p': metadata['p_scale'], 'et': metadata['et_scale'], 'n': 1.0, 'ndm': 1.0, 'lai': 1.0, 'etref': 1.0, 'r': 1.0, 'bf': 1.0, 'tr': 1.0, 'sr': 1.0, 'perc': 1.0, 'dperc': 1.0}
    var_name = key.split('_folder')[0]
    files = becgis.MatchProjResNDV(metadata['lu'], files, os.path.join(output_dir, var_name), resample = 'near', dtype = 'float32', scale = scales[var_name])
    complete_data[var_name] = (files, dates)
    return complete_data
    
def SortWaterPix(nc, variable, output_folder, time_var = 'time_yyyymm'):
    spa_ref = davgis.Spatial_Reference(4326)
    nc1 = netCDF4.Dataset(nc)
    time = nc1.variables[time_var][:]
    for time_value in time:
        output_dir = os.path.join(output_folder, variable)
        output_tif = os.path.join(output_dir, "{0}_{1}.tif".format(variable, time_value))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        davgis.NetCDF_to_Raster(input_nc=nc,
                                output_tiff=output_tif,
                                ras_variable=variable,
                                x_variable='longitude', y_variable='latitude',
                                crs=spa_ref,
                                time={'variable': time_var, 'value': time_value})
    return output_dir

def calc_missing_runoff_fractions(metadata):
    
    ID = metadata['id']
    accum = r"D:\WA_HOME\Loop_SW\Simulations\Simulation_{0}\Sheet_5\Acc_Pixels_CR_Simulation{0}_.nc".format(ID)
    
    outlets = r"D:\project_ADB\subproject_Catchment_Map\outlets\Basins_outlets_basin_{0}.shp".format(ID)
    inlets = r"D:\project_ADB\subproject_Catchment_Map\inlets\Basins_inlets_basin_{0}.shp".format(ID)
    
    basin_mask = r"D:\WA_HOME\Loop_SW\Simulations\Simulation_{0}\Sheet_5\Basin_CR_Simulation{0}_.nc".format(ID)
    
    sb_vector = r"D:/project_ADB/subproject_Catchment_Map/Basins_large/Subbasins_dissolved/dissolved_ID{0}.shp".format(ID)
    
    dico_in = metadata['dico_in']
    dico_out =  metadata['dico_out']

    output_fh =  r"C:\Users\bec\Desktop\03_test\empty.tif"
    
    geo_out, epsg, size_X, size_Y, size_Z, Time = RC.Open_nc_info(basin_mask)
    
    LA.Save_as_tiff(output_fh, np.zeros((size_Y, size_X)), geo_out, epsg)
          
    string = "gdal_rasterize -a Subbasins {0} {1}".format(sb_vector, output_fh)
    
    proc = subprocess.Popen(string, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    
    subs = becgis.OpenAsArray(output_fh, nan_values = True)
    total_size = np.nansum(subs[subs != 0] / subs[subs != 0])
    
    sizes = dict()
    total_out = dict()
    total_in = dict()
    ratios = dict()
    
    accumsin_boundary = list()
    accumsout_boundary = list()
    
    for sb in np.unique(subs[subs!=0]):
        
        sizes[sb] = np.nansum(subs[subs == sb]) / sb
        
        accumsin = list()
        accumsout = list()
        
        nc = netCDF4.Dataset(accum)
        driver = ogr.GetDriverByName('ESRI Shapefile')
        dataSource = driver.Open(outlets, 0)
        layer = dataSource.GetLayer()
        featureCount = layer.GetFeatureCount()
        for pt in range(featureCount):
            feature = layer.GetFeature(pt)
            subbasin = feature.GetField("id")
            if sb == int(subbasin):
                geometry = feature.GetGeometryRef()
                x = geometry.GetX()
                y = geometry.GetY()
                pos_x = (np.abs(nc.variables['longitude'][:]-x)).argmin()
                pos_y = (np.abs(nc.variables['latitude'][:]-y)).argmin()
                accumsout.append(nc.variables['Acc_Pixels_CR'][pos_y,pos_x])
                if 0 in dico_out[sb]:
                    accumsout_boundary.append(nc.variables['Acc_Pixels_CR'][pos_y,pos_x])
            if subbasin in dico_in[sb]:
                geometry = feature.GetGeometryRef()
                x = geometry.GetX()
                y = geometry.GetY()
                pos_x = (np.abs(nc.variables['longitude'][:]-x)).argmin()
                pos_y = (np.abs(nc.variables['latitude'][:]-y)).argmin()
                accumsin.append(nc.variables['Acc_Pixels_CR'][pos_y,pos_x])     
                
        total_out[sb] = np.sum(accumsout)
        
        if os.path.exists(inlets):
            
            nc = netCDF4.Dataset(accum)
            driver = ogr.GetDriverByName('ESRI Shapefile')
            dataSource = driver.Open(inlets, 0)
            layer = dataSource.GetLayer()
            featureCount = layer.GetFeatureCount()
            for pt in range(featureCount):
                feature = layer.GetFeature(pt)
                subbasin = feature.GetField("id")
                if sb == int(subbasin):
                    geometry = feature.GetGeometryRef()
                    x = geometry.GetX()
                    y = geometry.GetY()
                    pos_x = (np.abs(nc.variables['longitude'][:]-x)).argmin()
                    pos_y = (np.abs(nc.variables['latitude'][:]-y)).argmin()
                    accumsin.append(nc.variables['Acc_Pixels_CR'][pos_y,pos_x])
                    accumsin_boundary.append(nc.variables['Acc_Pixels_CR'][pos_y,pos_x])
        
        if len(accumsin) >= 1:
            total_in[sb] = np.sum(accumsin)
        else:
            total_in[sb] = 0.0
        
        ratios[sb] = (total_out[sb] - total_in[sb]) / sizes[sb]
    
    ratios['full'] = (np.sum(accumsout_boundary) - np.sum(accumsin_boundary)) / total_size
        
    return ratios