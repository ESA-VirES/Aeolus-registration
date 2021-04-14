#!/usr/bin/env python3
# -*- coding: iso-8859-1 -*

#pylint: disable=missing-docstring, line-too-long, empty-docstring, too-many-locals, invalid-name, trailing-newlines

#-------------------------------------------------------------------------------
#
# Project:          VirES-Aeolus
# Purpose:          Aeolus -- watch process for automatic registration of new products
# Authors:          Christian Schiller
# Copyright(C):     2017 - EOX IT Services GmbH, Vienna, Austria
# Email:            christian dot schiller at eox dot at
# Date:             2017-05-23
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
# Purpose:          Aeolus -- watch process for automatic registration of new products
# Authors:          Christian Schiller
# Copyright(C):     2017 - EOX IT Services GmbH, Vienna, Austria
# Email:            christian dot schiller at eox dot at
# Date:             2017-05-23
# License:          MIT License (MIT)

0.3: - this verion (0.3) requires a config-file as a cmd-line parameter
0.4: - changed to python 3

"""

from __future__ import print_function
import os
import sys
#import time
import datetime
import re
import signal
import traceback

import pyinotify

f_loc = os.path.dirname(os.path.realpath(__file__))
if not f_loc in sys.path:
    sys.path.append(f_loc)

from get_config import get_config
from aeolus_process_list import aeolus_process_product


__version__ = '0.4'
    # provide a *.ini file via cmd-line when starting routine
if len(sys.argv[1:]) == 1 and sys.argv[1].endswith('.ini'):
    watch_conf = get_config(sys.argv[1])
else:
    print("ERROR:  No config-file (*.ini) has been supplied")
    sys.exit(1)


    # some config-data
watch_dir = watch_conf['watch.watch_dir']
watch_log = watch_conf['watch.watch_log']
watch_pid = watch_conf['watch.watch_pid']
file_filter = watch_conf['watch.file_filter']


#global regex
regex = re.compile(file_filter)



class MyEventHandler(pyinotify.ProcessEvent):

    def my_init(self, file_object=sys.stdout):
        """
            automatically  constructor called from ProcessEvent.__init__(),
            extra arguments passed to __init__() will be delegated to my_init().
        """
        self._file_object = file_object


    def _now(self):
        """
            return a formatted time string
        """
        return '['+str(datetime.datetime.strftime(datetime.datetime.utcnow(), '%Y%m%dT%H%M%SZ')).strip()+'] -- '


    def process_IN_DELETE(self, event):
        """
            this is called if a file gets deleted, we like to log this
        """
        self._file_object.write(self._now() + 'Deleting: %s\n' % event.pathname)
        self._file_object.flush()


    def process_default(self, event):
        """
            this method is called for all others types of events.
            This method can be useful when an action fits all events.
        """
        pass


    def process_IN_MOVED_TO(self, event):
        """
            this method is called if an object is moved (in our case the zip-file
            is extracted in a temp-dir and then moved to the final location)
        """
        if regex.search(event.name):
            self._file_object.write(self._now() + 'Extracted file: %s\n' % event.pathname)

                # aeolus_process_product:
                # - checks if files are reprocessed, if collection exists
                # - calls the aeolus-register:
                #    - registers products
                #    - deregisters, removes extracted, reprocessed products (but not the ZIP-file)
                #    - delete existing product(s) from the file-system  (i.e. original ZIP-files and extracted data-files)
            #aeolus_process_product(self._file_object, event.path, event.name)
            try:
                aeolus_process_product(self._file_object, event.path, event.name)
            except Exception as exc:
                self._file_object.write('Error: %s\n' % (exc))
                traceback.print_exc(file=self._file_object)
            self._file_object.flush()


    def process_IN_CREATE(self, event):
        """
            this method is called if a file/directory was created in watched directory
        """
        if not event.pathname.endswith('.DBL'):
            if regex.search(event.name):
                self._file_object.write(self._now() + 'Copied file: %s\n' % event.pathname)
                try:
                    aeolus_process_product(self._file_object, event.path, event.name)
                except Exception as exc:
                    self._file_object.write('Error: %s\n' % (exc))
                    traceback.print_exc(file=self._file_object)
                self._file_object.flush()


    #def process_IN_CLOSE_WRITE(self, event):
        """
            method called after a file is created, written into, and then closed
            (an alternative to process_IN_MOVED_TO, e.g. if we would extract directy
            in the target-dir)
        """
        #target = os.path.join(event.path, event.name)
        #if regex.search(event.name):
            #self._file_object.write(  'Target: '+ target+'\n')
            #self._file_object.write("executing test_sub: "+ "\n")

                ## call the registration etc. ...
            #test_sub(self._file_object)
            #self._file_object.flush()



    # instantiate the class and notifier
#ff = file(watch_log, 'a')
myhandler = MyEventHandler(file_object=open(watch_log, 'a'))
#myhandler = MyEventHandler(file_object=sys.stdout)
wm = pyinotify.WatchManager()
notifier = pyinotify.Notifier(wm, myhandler)

#mask = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO
mask = pyinotify.IN_DELETE | pyinotify.IN_MOVED_TO
wm.add_watch(watch_dir, mask, rec=True, auto_add=True)


    # if started, ensure that there is only 1 daemon running
if os.path.exists(watch_pid):
    f = open(watch_pid, 'r')
    pid = f.readline()
    f.close()
    try:
        os.kill(int(pid[:-1]), signal.SIGHUP)
    except OSError:
        pass

    os.unlink(watch_pid)
    notifier.loop(daemonize=watch_conf['general.daemon'], pid_file=watch_pid, stderr=watch_log)
else:
    notifier.loop(daemonize=watch_conf['general.daemon'], pid_file=watch_pid, stderr=watch_log)


