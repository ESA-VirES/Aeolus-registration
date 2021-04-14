#!/usr/bin/env python3
# -*- coding: iso-8859-1 -*-

#pylint: disable=missing-docstring, line-too-long, empty-docstring, too-many-locals, invalid-name, trailing-newlines

#-------------------------------------------------------------------------------
#
# Project:          VirES-Aeolus
# Purpose:          Go through products and optimize not optimized products
# Authors:          Daniel Santillan
# Copyright(C):     2020 - EOX IT Services GmbH, Vienna, Austria
# Email:            daniel.santillan@eox.at
# Date:             2020-10-19
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


import os
import sys
import logging
import fcntl

from django.core.management import execute_from_command_line
from django.db import transaction
from django.conf import settings
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eoxs.settings")
# location of the the eoxserver instance
sys.path.append('/var/www/aeolus.services/production/eoxs')
sys.path.append('/var/www/aeolus.services/testing/eoxs')
sys.path.append('/var/www/aeolus.services/staging/eoxs')
sys.path.append('/var/www/vires/eoxs')

# mandatory Django initialization
django.setup()

# Initialize the EOxServer component system.
import eoxserver.core
eoxserver.core.initialize()

from eoxserver.resources.coverages import models
from eoxserver.resources.coverages.models import cast_eo_object
from eoxserver.backends import models as backends

from django.core.management import CommandError

from aeolus.models import OptimizedProductDataItem
from aeolus.optimize import create_optimized_file, OptimizationError


def instance_already_running(label="default"):
    """
    Detect if an an instance with the label is already running, globally
    at the operating system level.

    Using `os.open` ensures that the file pointer won't be closed
    by Python's garbage collector after the function's scope is exited.

    The lock will be released when the program exits, or could be
    released if the file pointer were closed.
    """

    lock_file_pointer = os.open(f"/tmp/instance_{label}.lock", os.O_WRONLY | os.O_CREAT)

    try:
        fcntl.lockf(lock_file_pointer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        already_running = False
    except IOError:
        already_running = True

    return already_running



def link_optimized_file(product, output_file, logger):
    logger.info(
        "Creating data item for optimized file '%s'" % output_file
    )
    # create a data item for the optimized file
    data_item, _ = OptimizedProductDataItem.objects.get_or_create(
        product=product,
        location=output_file, format="application/netcdf"
    )
    data_item.full_clean()
    data_item.save()

def optimize_file(product, output_file, logger):
    identifier = product.identifier
    product_type = product.product_type

    # get the filename for the data file

    try:
        input_file = product.product_data_items.get().location
    except backends.DataItem.DoesNotExist:
        raise CommandError(
            "No data file for product '%s' found" % product.identifier
        )

    link_optimized_file(product, output_file, logger)

    try:
        group_fields = create_optimized_file(
            input_file, product_type.name, output_file, False
        )
        for group, field_name in group_fields:
            logger.debug("Optimizing %s/%s" % (group, field_name))

        logger.info(
            "Successfully generated optimized file '%s'" % output_file
        )
    except OptimizationError as e:
        raise CommandError(
            "Failed to create the optimized file for product '%s'. "
            "Error was: %s" % (identifier, e)
        )


# init logger
log_file = "/var/log/vires/aeolus_optimize_data.log"

# create logger with 'spam_application'
log = logging.getLogger('aeolus_optimize_data')
log.setLevel(logging.INFO)
# create file handler which logs even debug messages
fh = logging.FileHandler(log_file)
fh.setLevel(logging.INFO)
# create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                              "%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
log.addHandler(fh)
log.addHandler(ch)

process_running = instance_already_running("aeolus_optimizing_process")

if not process_running:

    error_products = []
    unopt_list = models.Product.objects.filter(optimized_data_item=None).order_by('-begin_time')
    optimized_dir = getattr(settings, 'AEOLUS_OPTIMIZED_DIR', None)
    if optimized_dir:
        while len(unopt_list) != 0:
            curr_prod = unopt_list[0]
            curr_output_file = os.path.join(
                optimized_dir, curr_prod.product_type.name, curr_prod.identifier + '.nc'
            )
            try:
                with transaction.atomic():
                    optimize_file(curr_prod, curr_output_file, log)
            except Exception as e:
                error_products.append(curr_prod)
                log.error(
                    "Error optimizing file %s, optimizing will be skipped, error message %s"%(curr_prod.identifier, e)
                )

            # Query list again
            unopt_list = models.Product.objects.filter(optimized_data_item=None).order_by('-begin_time')
            # remove error products from list
            unopt_list = [p for p in unopt_list if p not in error_products]
else:
    log.warning("Optimizing process already running, this call will be ignored")
