#!/bin/bash

# Build script for Capacities Alfred Workflow

set -e

WORKFLOW_NAME="Capacities"
OUTPUT_FILE="${WORKFLOW_NAME}.alfredworkflow"

echo "Building ${WORKFLOW_NAME} Alfred Workflow..."

# Remove existing build file
if [ -f "$OUTPUT_FILE" ]; then
    rm "$OUTPUT_FILE"
    echo "Removed existing $OUTPUT_FILE"
fi

# Create the workflow package
zip -r "$OUTPUT_FILE" . \
    -x "*.git*" \
       "*.DS_Store*" \
       "*__pycache__*" \
       "*.pyc" \
       "*.log" \
       "prefs.plist" \
       "build.sh" \
       "$OUTPUT_FILE"

echo "✅ Successfully created $OUTPUT_FILE"
echo "📦 File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "To install:"
echo "1. Double-click $OUTPUT_FILE"
echo "2. Configure API token in Alfred workflow settings"
