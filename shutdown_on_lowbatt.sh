#!/bin/bash
source ~/.bashrc
set +v
set +x
tag=$(/bin/date +%Y.%m.%d.%H.%M.%S)
logfile=/var/log/user/shutdown_on_lowbatt.log 

# acpitool command produces:
#
# acpitool --ac_adapter
#  AC adapter     : off-line

result=$(acpitool --ac_adapter | egrep -e 'off-line')
if [[ X$result != X ]]
then
    # acpitool command produces:
    #
    # acpitool --battery
    #  Battery #1     : present
    #    Remaining capacity : unknown, 86.15%, 00:00:00
    #    Design capacity    : 6600 mA
    #    Last full capacity : 5907 mA, 89.50% of design capacity
    #    Capacity loss      : 10.50%
    #    Present rate       : 1140 mA
    #    Charging state     : Discharging
    #    Battery type       : Li-ion
    #    Model number       : DELL
    #    Serial number      : 1692
    level=$(acpitool --battery | grep Remaining | awk '{print $5}' | sed -e 's/[.].*$//')
    #
    # With the above acpitool output, level equal 86 after the pipeline: level=...
    #
    if [[ X$(echo $level | egrep -e '^[0-9]+$') != X ]]
    then
        echo "$tag: ACPITOOL SAYS BATTERY LEVEL IS $level PERCENT" >> $logfile
        if [[ $level -lt 17 ]]
        then
            /sbin/shutdown -h +3 '*** LOW BATTERY SHUTDOWN -- BATTERY CHARGE LESS THAN 17% ***'
            echo "$tag: ACPITOOL SAYS WE GOTTA SHUTDOWN" >> $logfile
            export DISPLAY=:0.0
            zenity --info --text '*** BATTERY LOW! GOING DOWN IN 3 MINUTES***'
        fi
    fi
fi
