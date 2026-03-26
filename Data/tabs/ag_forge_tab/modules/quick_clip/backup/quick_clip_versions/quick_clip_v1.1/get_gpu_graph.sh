#!/bin/bash

# This script gathers GPU usage and outputs it as a bar graph for the XFCE genmon panel.

# Get usage percentage using radeontop
# The '-l 1' flag makes it run once and exit.
USAGE_RAW=$(radeontop -d - -l 1)
USAGE_PERCENT_NUM="0"

if [ -n "$USAGE_RAW" ]; then
    # Extract the percentage string (e.g., "5.50%")
    USAGE_PERCENT_STR=$(echo "$USAGE_RAW" | grep -o 'gpu [0-9.]*%' | sed 's/gpu //')
    
    # Extract just the whole number for the bar graph
    if [ -n "$USAGE_PERCENT_STR" ]; then
        USAGE_PERCENT_NUM=$(echo "$USAGE_PERCENT_STR" | sed 's/%//' | awk '{printf "%.0f", $1}')
    fi
fi

# Output the special tag that genmon understands as a bar graph.
echo "<bar>$USAGE_PERCENT_NUM</bar>"
