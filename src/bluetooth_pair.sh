#!/usr/bin/env bash
if [[$1='']]
then
    echo "Pairing fail! MAC should be provided as a param to this script"
    exit -1
else
    sudo bash -c 'bluetoothctl << EOF
    power on
    discoverable on
    pairable on
    agent NoInputNoOutput
    default-agent
    trust $1
    pair $1
    EOF'
fi
exit 0