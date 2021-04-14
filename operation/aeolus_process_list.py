#!/usr/bin/env python3
# -*- coding: iso-8859-1 -*-

#pylint: disable=missing-docstring, line-too-long, empty-docstring, too-many-locals, invalid-name, trailing-newlines

#-------------------------------------------------------------------------------
#
# Project:          VirES-Aeolus
# Purpose:          Aeolus -- handle and analyse aeolus specific filenames
# Authors:          Christian Schiller
# Copyright(C):     2017 - EOX IT Services GmbH, Vienna, Austria
# Email:            christian dot schiller at eox dot at
# Date:             2019-09-02
# License:          MIT License (MIT)
#
#-------------------------------------------------------------------------------
# The MIT License (MIT):
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies of this Software or works derived from this Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#-------------------------------------------------------------------------------

"""
# Project:          VirES-Aeolus
# Purpose:          Aeolus -- handle and analyse aeolus specific filenames
# Authors:          Christian Schiller
# Copyright(C):     2017 - EOX IT Services GmbH, Vienna, Austria
# Email:            christian dot schiller at eox dot at
# Date:             2019-09-02
# License:          MIT License (MIT)



Usage:

    - No direct usage - is called from watch_data4reg.py (or watch_aux4reg.py)


WHAT:   called from watch_data4reg.py, which watches (via pyinotify) the data directory
        for the occurrence for new products
        - checks if products are reprocessed (see REPROCESSING-SCENARIOS, below)
        - deregister reprocessed products
        - register reprocessed products
        - delete old version of reprocessed products (TGZ-file and Data-file)
        - register new products
        - ensures that respective ProductCollection is available/created

added 2019-09-02:
        - added support to handle FTP-syncing without actually storing the ZIP-files permanently
0.7    - changed to python 3
"""


from __future__ import print_function
import os
import sys
import datetime
import fnmatch
import re


f_loc = os.path.dirname(os.path.realpath(__file__))
if not f_loc in sys.path:
    sys.path.append(f_loc)

from get_config import get_config
import aeolus_register
#from handle_checksum import remove_chksum_entry


__version__ = '0.7'
config = get_config('watch_data_config.ini')

ftp_config = get_config('ftp_data_config.ini')
chksum_input_file = ftp_config['local.chksum_file']


#-------------------------------------------------------------------------------
def now():
    """
        get a time string for messages/logging
    """
    return '['+str(datetime.datetime.strftime(datetime.datetime.utcnow(), '%Y%m%dT%H%M%SZ')).strip()+'] -- '



def findfile(inmask, path, recursive=True, splitpath=False):
    """
        find a file in a directory tree , including sub-dirs (default),
        simple wildcards *, ?, and character ranges expressed with [] will be matched
            Usage:  result = findfile(path, inmask, recursive=True, splitpath=True)
    """
    # print("I'm in "+sys._getframe().f_code.co_name)
    #logging.info("I am in "+sys._getframe().f_code.co_name)

    result = []
    if recursive is True:
        for root, _, files in os.walk(path):
            for ffile in files:
                if fnmatch.fnmatch(ffile, inmask):
                    if splitpath is False:
                        result.append(os.path.join(root, ffile))
                    else:
                        result.append([ffile, root])


    else:
        files = os.listdir(path)
        if splitpath is False:
            result = fnmatch.filter(files, inmask)
        else:
            res = fnmatch.filter(files, inmask)
            for elem in res:
                result.append([elem, path])

    return result





def aeolus_process_product(watch_log, inpath, inproduct):
    """
        aeolus specific filename processing to enable checking for existing/reprocessed data
        aeolus specific product registration
        aeolus specific deletion of products and TGZ-files at local-ftp storage
            (only for the production instance)
    """
    #print("I'm in "+sys._getframe().f_code.co_name)
    #watch_log.write('INPRODUCT: '+inproduct)

    if 'OPER_ALD_' in inproduct or 'OPER_AUX' in inproduct:
            # consider differernt fname-length of L1B (=63) and L2A/L2B (=59) plus their extension (DBL)
            # number of ('_') are: L1B (=9) and  L2A/L2B (=8)
                # for L1B & L2A
        if inproduct.count('_') == 9 and inproduct.endswith('DBL'):
            prod_id_to_chk = inproduct.rsplit('.', 1)[0].rsplit('_', 1)

                # for L2B/ L2C??  &  AUX_ZWC/AUX_MRC/AUX_RRC/AUX_ISR
        if inproduct.count('_') <= 8 and inproduct.endswith(('DBL', 'EEF')):
            prod_id_to_chk = inproduct.rsplit('.', 1)[0].rsplit('_', 1)

        fileending, col_name, range_type = deduct_prod_params(prod_id_to_chk[0])
        prod_status, product_match = identify_product_status(prod_id_to_chk[0])
        prod_status.sort()
        product_match.sort()

            # for debugging only
#        msg=inproduct+' '+fileending+' '+col_name+range_type #+' '+prod_status[0]+' '+product_match[0]
#        watch_log.write(now()+'DEBUG: '+msg)

            # there is a product with a differernt version number
        if len(prod_status[:]) > 1:
            for i in range(len(prod_status)):

                    # check if product is already registered
                chk_res = aeolus_register.check_id(prod_status[i][0]+'_'+prod_status[i][1]+fileending, watch_log)
                #watch_log.write(now()+'Check_Id: '+str(chk_res)+'\n')

                if (chk_res[0] == True) and  (chk_res[1] == 'Product'):
                    if int(prod_id_to_chk[1]) > int(prod_status[i][1]):
                            # product has a higher version number:
                            # remove also the optimized file
                        aeolus_register.aeolus_prod_optimize_delete(prod_status[i][0]+'_'+prod_status[i][1], watch_log)
                        watch_log.write(now()+'De-registering optimized product: '+ prod_status[i][0]+'_'+prod_status[i][1]+'.nc'+'\n')
                        watch_log.flush()
                            # deregister existing product
                        aeolus_register.dereg_prod(prod_status[i][0]+'_'+prod_status[i][1]+fileending, watch_log)
                        watch_log.write(now()+'De-registering: '+ prod_status[i][0]+'_'+prod_status[i][1]+fileending+'\n')
                        watch_log.flush()

                            # if this is the production instance (which handles the data) -> delete
                            # the TGZ-file and the corresponding data-file
                        if 'production' in config['instance.path']:
                                # delete TGZ-files in local-ftp
                            zname = os.path.join(product_match[i][1], product_match[i][0])
                            if zname.endswith('TGZ'):
                                delete_products(zname, watch_log, 'Deleting TGZ:')
                                # delete corresponding data file (cdf) in data-dir
                            pname = findfile(prod_status[i][0]+'_'+prod_status[i][1]+'*', config['local.data'])
                            delete_products(pname, watch_log, 'Deleting Product:')
                                # delete the corresponding optimized file
                            oname = findfile(prod_status[i][0]+'_'+prod_status[i][1]+'*', '/mnt/data/optimized')
                            delete_products(oname, watch_log, 'Removing optimized product: ')
                            # watch_log.write(now()+'Removing optimized product: '+ prod_status[i][0]+'_'+prod_status[i][1]+'.nc'+'\n')


            # always verify that the  Collection (col_name) exists (if set in config-file)
        if config['general.chk_coll'] is True:
            res = aeolus_register.check_id(col_name, watch_log)
            if res[0] is False:
                res = aeolus_register.make_vires_collection(col_name, range_type, watch_log)

            # register the new product
        aeolus_register.register_vires_product(inpath+'/'+inproduct, prod_id_to_chk[0]+'_'+prod_id_to_chk[1]+fileending, col_name, range_type, watch_log)

#### TODO ******************** OPTIMIZE **************
##            # generate an optimized data file (i.e. netCDF) -- only for  *.DBL files (l1B/L2A/L2B/AUX_MET [later also L2C])
##            # but optimization also works for AUX_ZWC (i.e. *.EEF)
#        if inproduct.endswith('DBL') or ("AUX_ZWC_1B") in inproduct:
#            aeolus_register.aeolus_prod_optimize(prod_id_to_chk[0]+'_'+prod_id_to_chk[1]+fileending, watch_log)
## *** End of Optimize ***

        #aeolus_register.register_vires_product(inpath+'/'+inproduct, str(prod_id_to_chk[0])+'_'+str(prod_id_to_chk[1])+fileending, col_name, range_type, watch_log)
        # delete the data products if it is a Non-OPER product
    elif 'production' in config['instance.path']:
        delete_products(inpath+'/'+inproduct, watch_log, 'Deleting Non-OPER Product:')



def identify_product_status(prod_id_to_chk):
    """
        check if incoming product is a new product or a reprocessed product
        since we can only check for exact eo_ids we need to compare the products
        with the files stored in the local-ftp to get their versions
    """
    # print("I'm in "+sys._getframe().f_code.co_name)
    #logging.info("I am in "+sys._getframe().f_code.co_name)

    prod_status = []
    product_match = get_local_ftp_listing(prod_id_to_chk)
    if len(product_match) > 0:
        for elem in product_match:
#                # <Removing ZIP-Storage>: for use with ZIP-files
#            fname = elem[0].rsplit('/',1)[0].rsplit('.',2)[0].rsplit('_',1)
                # <Removing ZIP-Storage>: for use with PRODUCT files (No-ZIPs)
            fname = elem[0].rsplit('/', 1)[0].rsplit('.', 1)[0].rsplit('_', 1)
#            if elem[0].count('_') == 9:
#                fname = elem[0].rsplit('/', 1)[0].rsplit('.', 1)[0].rsplit('_', 4)
#            elif elem[0].count('_') <= 8:
#                fname = elem[0].rsplit('/', 1)[0].rsplit('.', 1)[0].rsplit('_', 1)

            prod_status.append([fname[0], fname[1], elem[1]])

    return  prod_status, product_match



def get_local_ftp_listing(prod_id_to_chk):
    """
        get the listing of the local ftp, to see what product-version might already be registered
    """
    # print("I'm in "+sys._getframe().f_code.co_name)
    #logging.info("I am in "+sys._getframe().f_code.co_name)

        # <Removing ZIP-Storage>: for use with ZIP-files
#    product_match = findfile(prod_id_to_chk+'*', config['local.ftp_inpath'], splitpath=True)
        # <Removing ZIP-Storage>: for use with PRODUCT files
    product_match = findfile(prod_id_to_chk+'*', config['local.data'], splitpath=True)

    return product_match



def deduct_prod_params(prod_id_to_chk):
    """
        deduct:  fileending, collectionname, range_type
    """
    # print("I'm in "+sys._getframe().f_code.co_name)

    if prod_id_to_chk.count('_') == 8:
        collection = prod_id_to_chk.rsplit('_', 3)[0].split('_', 2)[-1]
    elif prod_id_to_chk.count('_') <= 7:
        collection = prod_id_to_chk.rsplit('_', 2)[0].split('_', 2)[-1]

    product_filters = [
        ('^AE_OPER_ALD_._N_1B',  'ALD_U_N_1B', ''),
        ('^AE_OPER_ALD_._N_2A',  'ALD_U_N_2A', ''),
        ('^AE_OPER_ALD_._N_2B',  'ALD_U_N_2B', ''),
        ('^AE_OPER_ALD_._N_2C',  'ALD_U_N_2C', ''),
        ('^AE_OPER_AUX_ZWC',     'AUX_ZWC_1B', ''),
        ('^AE_OPER_AUX_RRC',     'AUX_RRC_1B', ''),
        ('^AE_OPER_AUX_MRC',     'AUX_MRC_1B', ''),
        ('^AE_OPER_AUX_ISR',     'AUX_ISR_1B', ''),
        ('^AE_OPER_AUX_MET_12_', 'AUX_MET_12', '')
    ]

    for prod_type, range_type, ending in product_filters:
        match = re.match(prod_type, prod_id_to_chk)
        if match:
            #return prod_type, collection, ending
            return ending, collection, range_type

    raise Exception("No product type pattern matched!")



def delete_products(del_prod_list, watch_log, msg):
    """
        delete existing product(s) from the file-system
        (i.e. original TGZ-files or extracted data-files)
    """
    # print("I'm in "+sys._getframe().f_code.co_name)
    #logging.info("I am in "+sys._getframe().f_code.co_name)

    if isinstance(del_prod_list, list):
        for elem in del_prod_list:
            if os.path.isfile(elem):
                try:
                    os.remove(elem)
                    watch_log.write(now()+msg+' -- '+elem+'\n')
                        ## remove md5sum entry
                    fname = elem.rsplit('/', 1)
                        # use only the 'basename' to avoid troubles with slashes in sed
#                    remove_chksum_entry(chksum_input_file, fname[1])
#                    watch_log.write(now()+'[INFO] - Removed chksum entry - '+elem)

                except (IOError, OSError, Exception) as e:
                    #watch_log.write(now()+'[ERROR] - Could not delete: '+ elem+'\n')
                    watch_log.write(now()+'[ERROR] - Could not delete: '+ elem+' -- '+str(e)+'\n')

    elif isinstance(del_prod_list, str):
        if os.path.isfile(del_prod_list):
            try:
                os.remove(del_prod_list)
                watch_log.write(now()+msg+' -- '+del_prod_list+'\n')
                    ## remove md5sum entry
                fname = del_prod_list.rsplit('/', 1)
                    # use only the 'basename' to avoid troubles with slashes in sed
#                remove_chksum_entry(chksum_input_file, fname[1])
#                watch_log.write(now()+'[INFO] - Removed chksum entry - '+elem)

            except (IOError, OSError, Exception) as e:
                #watch_log.write(now()+'[ERROR] - Could not delete: '+del_prod_list+'\n')
                watch_log.write(now()+'[ERROR] - Could not delete: '+del_prod_list+' -- '+str(e)+'\n')

    watch_log.flush()
    return

