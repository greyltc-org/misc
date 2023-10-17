#!/usr/bin/env bash
# fan speed control script for Dell servers.
# inspired by content from https://web.archive.org/web/20231016031641/https://www.spxlabs.com/blog/2019/3/16/silence-your-dell-poweredge-server
# requires ipmitool

INPUT="${1}"  # [% of max speed]

HOST="idrac-changeme"
LOGIN="root"
LOGINPW="a very strong password"
MIN_SPEED=20  # for safety, don't let the user go below this [% of max speed]

if test "${INPUT}" -eq 0; then
        echo "Auto fan control"
        # set fans to auto control mode
        ipmitool -I lanplus -H "${HOST}" -U "${LOGIN}" -P "${LOGINPW}" raw 0x30 0x30 0x01 0x01
elif test "${INPUT}" -ge ${MIN_SPEED} -a "${INPUT}" -le 100; then
        echo "Fan speed fixed to ${INPUT}%"
        # set fans to manual control mode
        ipmitool -I lanplus -H "${HOST}" -U "${LOGIN}" -P "${LOGINPW}" raw 0x30 0x30 0x01 0x00
        # set speed of all fans to INPUT percent
        ipmitool -I lanplus -H "${HOST}" -U "${LOGIN}" -P "${LOGINPW}" raw 0x30 0x30 0x02 0xff "0x$(printf '%x\n' ${INPUT})"
else
        echo "Bad input: ${INPUT}"
fi
