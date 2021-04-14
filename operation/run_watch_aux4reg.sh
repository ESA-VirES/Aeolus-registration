#!/bin/bash

## watch for incoming Aeolus AUX datasets and register them

source /var/www/<domain>/<environment>/virtualenv/bin/activate && /bin/python3 /usr/local/vires/ftp_mirror_and_register/watch_data4reg.py  /usr/local/vires/ftp_mirror_and_register/watch_aux_config.ini

