#!/bin/bash
# Health check script for Qolsys Gateway container
#
# This script checks if the gateway application is running properly.
# Returns 0 (success) if healthy, 1 (failure) if unhealthy.

set -e

# Check if the Python process is running
if ! pgrep -f "python -m apps.qolsysgw" > /dev/null 2>&1; then
    echo "ERROR: Gateway process not running"
    exit 1
fi

# TODO: Add checks for MQTT and panel connectivity when health endpoint is implemented
# For now, just verify the process exists

echo "OK: Gateway process is running"
exit 0