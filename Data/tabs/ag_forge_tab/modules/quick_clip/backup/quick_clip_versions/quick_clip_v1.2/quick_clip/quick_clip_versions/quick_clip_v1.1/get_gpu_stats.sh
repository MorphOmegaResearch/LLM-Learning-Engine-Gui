#!/bin/bash

# This script gathers GPU temperature and usage for display in an XFCE genmon panel.

# Find the correct hwmon directory for the amdgpu driver
# This makes the script robust against reboots where the number might change.
HWMON_PATH=$(grep -l "amdgpu" /sys/class/hwmon/hwmon*/name | sed 's|/name$||')

TEMP="N/A"
if [ -n "$HWMON_PATH" ] && [ -f "$HWMON_PATH/temp1_input" ]; then
    # Read temperature in millidegrees and convert to Celsius
    TEMP_RAW=$(cat "$HWMON_PATH/temp1_input")
    TEMP=$(awk -v temp="$TEMP_RAW" 'BEGIN {printf "%.0f°C", temp/1000}')
fi

# Get usage percentage using radeontop
# The '-l 1' flag makes it run once and exit.
USAGE_RAW=$(radeontop -d - -l 1)
USAGE="N/A"
if [ -n "$USAGE_RAW" ]; then
    USAGE=$(echo "$USAGE_RAW" | grep -o 'gpu [0-9.]*%' | sed 's/gpu //')
fi

echo "GPU: $USAGE / $TEMP"
