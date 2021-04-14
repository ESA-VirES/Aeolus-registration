#/bin/bash

## TODO:
##  - create 'dj_syncing_user' on both servers (-> NO homedir!)
##  - crate certificate for 'dj_syncing_user'
##  - add '-q' to scp & ssh lines
##  - add  '2>&1'  to calls with logfile
##



scriptname=$(basename "$0")

##
## script to export all users from the ACTIVE Aeolus-Server and import it to the FALLBACK Aeolus-Server
##  - the script is intended to be run as root
##  - the script is intended to be run from a cron-job
##

## PROPOSAL
##   - a SPECIAL USER should be created in the sudoers with the only right to run this script as root


DOMAIN='aeolus.services'
INSTANCE='production'
#LOGFILE='/home/schillerc/SYNC_USER_TEST.log'
LOGFILE='/var/log/vires/user_sync/dj_syncing_users.log'
EXPORTFILE="dj_users_export.json"

SYNC_USER='schillerc'                   ## for testing
#SYNC_USER='dj_sync_user'
SYNC_USER_CERT="/home/$SYNC_USER/.ssh/vires_datasync"



#------------------------
fhost=$(hostname -f)
shost=$(hostname -s)
eoxs_dir="/var/www/$DOMAIN/$INSTANCE/eoxs"
sync_user_id=$(id $SYNC_USER -u)


if [ "${shost:${#shost}-1:1}" -eq 1 ]; then
    targethost=${fhost/1/3}
else
    targethost=${fhost/3/1}
fi




function usage() {
    echo "Usage:  script to export all users from the ACTIVE Aeolus-Server and import it to the FALLBACK Aeolus-Server"
    echo "   $scriptname "
    exit
}

function now () {
    date +%Y%m%dT%H%M%SZ
}

function is_sync_user () {
    if [ "$(id -u)" != "$sync_user_id" ]; then
        echo "Sorry, this script needs to be run as User:  $SYNC_USER --> use sudo -u $SYNC_USER $scriptname"
        exit 1
    fi

}


# check if we are runing as sync_user
is_sync_user
tmpdir=$(mktemp -d -p /tmp  user_syncing_XXXXXX)



    # export all users
echo "["$(now)"] - User sync: Starting"  >>  $LOGFILE
python3 $eoxs_dir/manage.py auth_export_users -f $tmpdir/$EXPORTFILE  >> $LOGFILE 2>&1

if [ "$?" -eq "0" ]; then
    echo "["$(now)"] - User sync: Export done"  >>  $LOGFILE
else
    echo "["$(now)"] - ERROR: User sync: Export failed"  >>  $LOGFILE
    exit 2
fi


    # copy user-export to tagethost
scp -q -r -i $SYNC_USER_CERT  $tmpdir $SYNC_USER@$targethost:/tmp/

if [ "$?" -eq "0" ]; then
    echo "["$(now)"] - User sync: Copying export file to $targethost done"  >>  $LOGFILE
else
    echo "["$(now)"] - ERROR: User sync: Copying export file to $targethost failed"  >>  $LOGFILE
    exit 3
fi



    # execute the user import on targethost  =>>   2>&1
ssh -q -i $SYNC_USER_CERT -A -t -t  -R 7000:localhost:22  $SYNC_USER@$targethost "echo ["$(now)"] - User sync: Import starting  >>  $LOGFILE; sudo -u $SYNC_USER python3 $eoxs_dir/manage.py auth_import_users -f $tmpdir/$EXPORTFILE >> $LOGFILE 2>&1 ; echo ["$(now)"] - User sync: Import done  >> $LOGFILE; sed -e '/updated$/ d' -i $LOGFILE"
## used just for testing
#ssh -q -i $SYNC_USER_CERT -A -t -t  -R 7000:localhost:22  $SYNC_USER@$targethost "echo ["$(now)"] - User sync: Import starting  >>  $LOGFILE; sudo -u $SYNC_USER python3 $eoxs_dir/manage.py producttype list >> $LOGFILE 2>&1; echo ["$(now)"] - User sync: Import done  >> $LOGFILE"

if [ "$?" -eq "0" ]; then
    echo "["$(now)"] - User sync: Import done"  >>  $LOGFILE
else
    echo "["$(now)"] - ERROR: User sync: Import failed"  >>  $LOGFILE
    exit 4
fi




    # targethost - cleanup the user-export file
ssh -q -i $SYNC_USER_CERT -A -t -t  -R 7000:localhost:22  $SYNC_USER@$targethost "sudo -u $SYNC_USER /bin/rm -r $tmpdir; echo ["$(now)"] - User sync: Removing export file done  >>  $LOGFILE  2>&1"

if [ "$?" -eq "0" ]; then
    echo "["$(now)"] - User sync: Removing export file done"  >>  $LOGFILE
else
    echo "["$(now)"] - ERROR: User sync: Removing export file failed"  >>  $LOGFILE
    exit 5
fi




## local cleanup
/bin/rm -r $tmpdir

if [ "$?" -eq "0" ]; then
    echo "["$(now)"] - User sync: Finished"  >>  $LOGFILE
    exit 0
else
    echo "["$(now)"] - ERROR: User sync: Removing export file failed"  >>  $LOGFILE
    exit 6
fi


