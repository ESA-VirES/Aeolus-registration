#!/bin/bash


# script to check if products in the optimized directory (SSD) are older than given 'timerange'
#   *) if yes: - move file to HDD
#      - create symlink from SSD to HDD
#   *) if no:  - do nothing



# keep 300 days worth of data on the SSD - move the rest to the HDD and create a SymLink
timerange=300
logfile='/var/log/vires/move_optimized2hdd_symlinks.log'

# data locations
ssd_opti='/mnt/data/optimized'
hdd_opti='/mnt/data/hdd/optimized'

prod_dirs='ALD_U_N_1B ALD_U_N_2A ALD_U_N_2B ALD_U_N_2C AUX_ZWC_1B AUX_MET_12'
#prod_dirs='ALD_U_N_1B ALD_U_N_2A ALD_U_N_2B ALD_U_N_2C AUX_ZWC_1B'

# this script needs only to be run on 'aeolus.serv3.eox.at' to save space on the SDD
if [ $(hostname -f) == "aeolus-serv1.eox.at" ]; then
    exit
fi


#-------------------

function now(){
  date +%Y%m%dT%H%M%SZ
}

function today() {
    today=$(date +%Y%m%d)
    target_date=$(date +%Y%m%d -d -"$timerange"days)
}


#---------------------------------------
#  main
#---------------------------------------

NOW=$(now)
PWD=$(pwd)

# get target_date
today

echo $target_date

for dir in $prod_dirs; do
    cd $ssd_opti'/'$dir
    flist=$(ls -1 )
    move_list=''
    for elem in $flist; do
        if [ ${elem:19:8} -lt $target_date ]; then
            if  [ -f $elem ] && [ ! -h $elem ]; then
                move_list+=$elem' '
            fi
        fi
    done

    cnt=0
    for elem in $move_list; do
        cnt=$(( cnt + 1 ))
    done
    echo "$dir -- "$cnt

    for ff in $move_list; do
        /bin/mv  $ff  $hdd_opti'/'$dir
#echo "/bin/mv  $ff  $hdd_opti'/'$dir'/'" >> '/var/log/vires/move_optimized2hdd_TEST.log'
        if [ $? -eq 0 ]; then
            echo '['$(now)'] - Moving product to HDD: '$hdd_opti'/'$dir'/'$ff  >> $logfile
        else
            echo '['$(now)'] - Error moving file to HDD: '$hdd_opti'/'$dir'/'$ff  >> $logfile
        fi

        /bin/ln -s  $hdd_opti'/'$dir'/'$ff  $ff
#echo "/bin/ln -s  $hdd_opti'/'$dir'/'$ff  $ff" >> '/var/log/vires/move_optimized2hdd_TEST.log'
        if [ $? -eq 0 ]; then
            echo '['$(now)'] - Creating SymLink to product: '$hdd_opti'/'$dir'/'$ff ' --> '$ff  >> $logfile
        else
            echo '['$(now)'] - Error creating SymLink: '$ff  >> $logfile
        fi
    done

done


echo '*** DONE ***'


