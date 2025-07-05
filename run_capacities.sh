#!/bin/bash

# Alfred Capacities Workflow Runner
cd "$(dirname "$0")"

# Find Python3 and run the script
if command -v python3 &> /dev/null; then
    python3 capacities.py "$1"
elif command -v /opt/homebrew/bin/python3 &> /dev/null; then
    /opt/homebrew/bin/python3 capacities.py "$1"
elif command -v /usr/bin/python3 &> /dev/null; then
    /usr/bin/python3 capacities.py "$1"
else
    echo '{"items": [{"title": "Error", "subtitle": "Python3 not found", "valid": false}]}'
fi