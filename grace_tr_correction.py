# -*- coding: utf-8 -*-
"""
Created on Tue Dec 19 09:47:04 2017

@author: bec
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import re
import pandas as pd
import scipy.optimize as optimization
from datetime import datetime
from scipy import interpolate
from WA_Hyperloop import becgis


def get_ts_from_complete_data(complete_data, mask, keys):
    
    common_dates = becgis.CommonDates([complete_data[key][1] for key in keys])
    becgis.AssertProjResNDV([complete_data[key][0] for key in keys])
    
    MASK = becgis.OpenAsArray(mask, nan_values = True)
    
    tss = dict()
    
    for key in keys:
        
        var_mm = np.array([])
        
        for date in common_dates:
            
            tif = complete_data[key][0][complete_data[key][1] == date][0]
            
            DATA = becgis.OpenAsArray(tif, nan_values = True)
            
            DATA[np.isnan(MASK)] = np.nan
            
            var_mm = np.append(var_mm, np.nanmean(DATA))
        
        tss[key] = (common_dates, var_mm)

    return tss


def calc_var_correction(metadata, complete_data, output_dir, formula = 'p-et-tr+supply_sw', plot = True):

    a_guess = np.array([1.0])
    
    output_dir = os.path.join(output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    keys, operts = split_form(formula)
    
    tss = get_ts_from_complete_data(complete_data, metadata['lu'], keys)
    
    grace = read_grace_csv(metadata['GRACE'])
    grace = interp_ts(grace, tss[keys[0]])

    msk = ~np.isnan(grace[1])


    def func(x, a):
        
        ds = np.zeros(msk.sum())
        for key, oper in zip(keys, operts):
            if key == keys[-1]:
                new_data = tss[key][1][msk][x] * a
            else:
                new_data = tss[key][1][msk][x]
            
            if oper == '+':
                ds += new_data
            elif oper == '-':
                ds -= new_data
            elif oper == '/':
                ds /= new_data
            elif oper == '*':
                ds *= new_data
            else:
                raise ValueError('Unknown operator in formula')
        
        return np.cumsum(ds)


    x = range(msk.sum())

    a,b = optimization.curve_fit(func, x, grace[1][msk], a_guess, bounds = (0, np.inf))                    
    
    new = keys[-1]+'_new'
    tss[new] = (tss[keys[-1]][0], a[0]*tss[keys[-1]][1])
    formula_dsdt_new = formula.replace(keys[-1], new)
    
    path = os.path.join(output_dir, metadata['name'], metadata['name'])
    
    if plot:
        plot_optimization(grace, func, a, x, keys[-1])
        plt.savefig(path + '_optimization.png')
        plt.close()
        
        plot_storage(tss, formula, grace, a_guess)
        plt.savefig(path + '_orig_dsdt.png')
        plt.close()
        
        plot_cums(tss, grace, formula, formula_dsdt_new)
        plt.savefig(path + '_cumulatives_wb.png')
        plt.close()
        
        plot_storage(tss, formula_dsdt_new, grace, a)
        plt.savefig(path + '_corr_dsdt.png')
        plt.close()

    return a


def correct_var(metadata, complete_data, output_dir, formula):
    var = split_form(formula)[0][-1]
    a = calc_var_correction(metadata, complete_data, output_dir, formula = formula, plot = True)
    for fn in complete_data[var][0]:
        geo_info = becgis.GetGeoInfo(fn)
        data = becgis.OpenAsArray(fn, nan_values = True) * a[0]
        becgis.CreateGeoTiff(fn, data, *geo_info)


def toord(dates):
    return np.array([dt.toordinal() for dt in dates[0]])


def interp_ts(source_ts, destin_ts):
    f = interpolate.interp1d(toord(source_ts), source_ts[1], 
                             bounds_error = False, fill_value = np.nan)
    values = f(toord(destin_ts))
    return (destin_ts[0], values)


def read_grace_csv(csv_file):
    
    df = pd.read_csv(csv_file)
    dt = [datetime.strptime(dt, '%Y-%m-%d').date() for dt in df['date'].values]
    grace_mm = np.array(df['dS [mm]'].values)
    
    return np.array(dt), grace_mm


def plot_optimization(grace, func, a, x, title):
    plt.grid(b=True, which='Major', color='0.65',linestyle='--', zorder = 0)
    plt.plot(*grace, label = 'target')
    plt.plot(grace[0], func(x,a[0]), label = 'optimized')
    plt.plot(grace[0], func(x,1), label = 'original')
    plt.suptitle('a = {0}'.format(a[0]))
    plt.title(title)
    plt.legend()

def plot_storage(tss, formula, grace, a):

    varias = re.split("\W", formula)
    
    plt.figure(figsize = (10,8))
    plt.clf()
    
    ax1 = plt.gca()
    ax2 = ax1.twinx()
    
    linestyles = ['-', '--', '-.', ':']
    
    for i, vari in enumerate(varias):
        ax1.plot(*tss[vari], linestyle=linestyles[i], color='k', label=vari)
    
    dstoragedt = calc_form(tss, formula)
    storage = (dstoragedt[0], np.cumsum(dstoragedt[1]))
    
    ax2.plot(*storage, linestyle='-', color='r', label='Storage (WB)')
    ax2.plot(*calc_polyfit(storage), linestyle=':', color='r')
    
    if grace:
        ax2.plot(*grace, linestyle='--', color='r', label='Storage (GRACE)')
        ax2.plot(*calc_polyfit(grace), linestyle=':', color='r')
    
    ax1.set_ylabel('Flux [mm/month]')
    ax2.set_ylabel('S [mm]')
    
    plt.xlabel('Time')
    plt.title('dSdt = {0}, {1} = {2} * tr'.format(formula,
              varias[-1], a[0]))
    ax1.legend(loc = 'upper left')
    ax2.legend(loc = 'upper right')


def plot_cums(tss, storage, formula_dsdt, formula_dsdt_new):
    plt.figure(figsize = (10,8))
    plt.clf()
    plt.grid(b=True, which='Major', color='0.65',linestyle='--', zorder = 0)
    
    keys = split_form(formula_dsdt)[0]
    
    for key in keys:
        plt.plot(tss[key][0], np.cumsum(tss[key][1]),
                 label = '$\sum {0}$'.format(key))
    
    new = keys[-1]+'_new'
    plt.plot(tss[new][0], np.cumsum(tss[new][1]),
             label = '$\sum {0}_{1}$'.format(keys[-1], r'{corr}'))
    
    msk = ~np.isnan(storage[1])
    plt.plot(storage[0][msk], storage[1][msk], label = 'S_grace')
    
    dsdt_orig = calc_form(tss, formula_dsdt)
    plt.plot(dsdt_orig[0], np.cumsum(dsdt_orig[1]), label = 'S_orig')
    
    dsdt_new = calc_form(tss, formula_dsdt_new)
    plt.plot(dsdt_new[0], np.cumsum(dsdt_new[1]), label = 'S_corr')
    
    plt.xlabel('Time')
    plt.ylabel('Stock [mm]')
    plt.legend()  


def calc_polyfit(ts, order = 1):
    dts_ordinal = toord(ts)
    p = np.polyfit(dts_ordinal[~np.isnan(ts[1])],
                               ts[1][~np.isnan(ts[1])], order)
    vals = np.polyval(p, dts_ordinal)
    dts = [datetime.fromordinal(dt).date() for dt in dts_ordinal]
    return (dts, vals)


def calc_form(tss, formula):
    
    varias, operts = split_form(formula)
        
    assert len(varias) == len(operts)
    
    ds = np.zeros(tss[varias[0]][0].shape)
    
    for vari, oper in zip(varias, operts):
        
        if oper == '+':
            ds += tss[vari][1]
        elif oper == '-':
            ds -= tss[vari][1]
        elif oper == '/':
            ds /= tss[vari][1]
        elif oper == '*':
            ds *= tss[vari][1]
        else:
            raise ValueError('Unknown operator in formula')
    
    return (tss[varias[0]][0], ds)


def split_form(formula):
    varias = re.split("\W", formula)
    operts = re.split("[a-z]+", formula, flags=re.IGNORECASE)[1:-1]
    
    while '_' in operts:
        operts.remove('_')
        
    if len(varias) > len(operts):
        operts.insert(0, '+')
    
    return varias, operts





