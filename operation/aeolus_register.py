#!/usr/bin/env python3
# -*- coding: iso-8859-1 -*-

#pylint: disable=missing-docstring, line-too-long, empty-docstring, too-many-locals, invalid-name, trailing-newlines

#-------------------------------------------------------------------------------
#
# Project:          VirES-Aeolus
# Purpose:          Deregister/Register data updated from a ftp-mirror site
# Authors:          Christian Schiller
# Copyright(C):     2017 - EOX IT Services GmbH, Vienna, Austria
# Email:            christian dot schiller at eox dot at
# Date:             2018-09-05
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
# Purpose:          Deregister/Register data updated from a ftp-mirror site
# Authors:          Christian Schiller
# Copyright(C):     2017 - EOX IT Services GmbH, Vienna, Austria
# Email:            christian dot schiller at eox dot at
# Date:             2018-09-05
# License:          MIT License (MIT)


Usage:

    - No direct usage - is called from aeolus_process_list.py

0.7:   - changed to python 3
"""


import os
import sys
#import time
import datetime
import subprocess
import logging

from django.core.management import execute_from_command_line
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eoxs.settings")
    # location of the the eoxserver instance
sys.path.append('/var/www/aeolus.services/production/eoxs')
#sys.path.append('/var/www/aeolus.services/production/eoxs')

    # mandatory Django initialization
django.setup()

    # Initialize the EOxServer component system.
import eoxserver.core
eoxserver.core.initialize()

from eoxserver.resources.coverages import models
from eoxserver.resources.coverages.models import cast_eo_object

from django.core.management import CommandError

__version__ = '0.7'



#-------------------------------------------------------------------------------
def now():
    """
        get a time string for messages/logging
    """
    timestamp = datetime.datetime.utcnow()
    timestr = datetime.datetime.strftime(timestamp, '%Y%m%dT%H%M%SZ')
    return '[%s] -- ' % timestr



def check_id(prod_id, watch_log):
    """
        check if a Product is registered
    """
    # print("I'm in "+sys._getframe().f_code.co_name)

    ObjectType = getattr(models, "EOObject")
    try:
        obj = ObjectType.objects.get(identifier=prod_id)
        watch_log.write('check_id: '+prod_id+' -- '+str(obj)+'\n')
        watch_log.flush()
        #return  [True, obj.real_type.__name__]
        return  [True, type(cast_eo_object(obj)).__name__]
    except ObjectType.DoesNotExist as e:
        watch_log.write('check_id - Not registered: '+prod_id+' -- '+str(e)+'\n')
        watch_log.flush()
        return  [False, None]



def make_vires_collection(coll_id, range_type, watch_log):
    """
        create a vires dataset_series/collection
    """
    # print("I'm in "+sys._getframe().f_code.co_name)

    try:
        execute_from_command_line([
            'manage.py',
            'aeolus_collection_create',
            '-i',
            coll_id,
            '-r',
            range_type
        ])
        watch_log.write('Creating Collection: '+coll_id+'\n')
        watch_log.flush()
    except Exception as e:
        watch_log.write('[Error] - Creating collection: '+str(e)+'\n')
        watch_log.flush()

    return


def link_public_product(prod_id, coll_name, logging):
    """
        link an aeolus product to public collection
    """
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id)
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id, file=watch_log)

    try:
        lresult = subprocess.check_output(["python3", "/var/www/aeolus.services/production/eoxs/manage.py", 'collection', 'insert', coll_name, prod_id, '--use-extent'])
        l_result = list(lresult.decode().split('\n'))
        l_result.remove('')

        logging.info("%s" % l_result[0])
    except CommandError as ce:
        pass
    except Exception as e:
        logging.error('[Error] - Link_status: '+str(e)+'\n')
    
    return



def unlink_public_product(prod_id, coll_name, logging):
    """
        link an aeolus product to public collection
    """
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id)
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id, file=watch_log)

    try:
        execute_from_command_line([
            'manage.py',
            'collection',
            'exclude',
            coll_name,
            prod_id
        ])
        logging.info(now() + 'UnLinking Public Aeolus Product: '+str(prod_id)+' -> '+coll_name+'\n')
    except Exception as e:
        logging.error('[Error] - UnLink_status: '+str(e)+'\n')


    return



def register_vires_product(prod_loc, prod_id, coll_name, range_type, watch_log):
    """
        register a vires product
    """
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id)
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id, file=watch_log)

    try:
        execute_from_command_line([
            'manage.py',
            'aeolus_product_add',
            '--simplify',
            '0.2',
            '--collection',
            coll_name,
            prod_loc,
            '--conflict=REPLACE'
        ])
        watch_log.write(now() + 'Registered Aeolus Product: '+str(prod_id)+'\n')
        watch_log.flush()
    except Exception as e:
        watch_log.write('[Error] - Register_status: '+str(e)+'\n')
        watch_log.flush()
        watch_log.write('[Error] - Register_status: '+str(e)+'\n')
        watch_log.flush()

    return



def aeolus_prod_optimize(prod_id, watch_log):
    """
        generate an optimized (netCDF) file of the aeolus product
    """
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id)aeolus_process_product
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id, file=watch_log)

    try:
        execute_from_command_line([
            'manage.py',
            'aeolus_product_optimize',
            '-i',
            prod_id,
            '--refresh'
        ])
        watch_log.write(now() + 'Optimized Aeolus Product: '+str(prod_id)+'\n')
        watch_log.flush()
    except Exception as e:
        watch_log.write('[Error] - Optimizing_status: '+str(e)+'\n')
        watch_log.flush()

    return



def aeolus_prod_optimize_delete(prod_id, watch_log):
    """
        generate an optimized (netCDF) file of the aeolus product
    """
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id)
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id, file=watch_log)

    try:
        execute_from_command_line([
            'manage.py',
            'aeolus_product_optimize',
            '-d',
            '-i',
            prod_id
        ])
        watch_log.write(now() + 'Deleted Optimized Aeolus Product: '+str(prod_id)+'\n')
        watch_log.flush()
    except Exception as e:
        watch_log.write('[Error] - Optimizing_status: '+str(e)+'\n')
        watch_log.flush()

    return



def dereg_prod(prod_id, watch_log):
    """
        de-register an existing product
    """
    # print("I'm in "+sys._getframe().f_code.co_name, prod_id)

    try:
        product = models.Product.objects.get(identifier=prod_id)
            # final removal
        product.delete()
        watch_log.write(now() + 'De-Registering: '+str(product)+'\n')
    except models.Product.DoesNotExist:
        watch_log.write(now() + '[ERROR] - Could not De-Register: '+ str(product)+'\n')

    watch_log.flush()
    return



#def get_registered_products_list(prod_type="Products"):
def get_registered_products_list():
    """
        get a (sorted) listing of registered Products / Collections / ForwardModel
          - this function is intended for interactive use, there is not logging supported
          - the respective listing is written to a file
     TODO: this is not working - there is no list returned --> needs to be changed to uswe a subprocess
    """
    # print("I'm in "+sys._getframe().f_code.co_name)

    listing = None
    try:
        listing = execute_from_command_line([
            'manage.py',
            'id',
            'list'
        ])
    except Exception as e:
        print(('ERROR -- List could not be produced --> ', e))

    return listing



def get_public_collection_list(coll_names, logging):
    """
        get a list of all products which are linked to one of the XXXX_public Collections
    """
    # print("I'm in "+sys._getframe().f_code.co_name)

    coll_list = []
    for coll in coll_names:
        try:
            #clist = execute_from_command_line([ 'manage.py', 'id', 'list', '--collection', coll ])
            clist = subprocess.check_output(["python3", "/var/www/aeolus.services/production/eoxs/manage.py", 'id', 'list', '--collection', coll])
            c_list = list(clist.decode().split('\n'))
            c_list.remove('')

            for elem in c_list:
                coll_list.append(elem.rstrip(' Product'))

            logging.info(now() + 'Getting Public Products list for Collection - '+coll)
        except Exception as e:
            logging.error('[Error] - Getting Public Products list for Collection - '+coll+' - '+ str(e)+'\n')

    return coll_list





