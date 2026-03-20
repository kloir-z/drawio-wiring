#!/bin/bash
# Generate a .drawio diagram and convert to PNG for preview.
#
# Usage:
#   tools/preview.sh sandbox/my_script.py
#
# This runs the gen script, then converts the output .drawio to PNG.
# The PNG is saved next to the .drawio file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 1 ]; then
  echo "Usage: tools/preview.sh <gen_script.py>" >&2
  exit 1
fi

GEN_SCRIPT="$1"

# Run the generation script
echo "Running: python3 $GEN_SCRIPT"
python3 "$GEN_SCRIPT"

# Find the .drawio file (most recently modified in the same directory)
SCRIPT_DIR_OF_GEN="$(dirname "$GEN_SCRIPT")"
DRAWIO_FILE=$(find "$SCRIPT_DIR_OF_GEN" -maxdepth 1 -name '*.drawio' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

if [ -z "$DRAWIO_FILE" ]; then
  echo "Error: No .drawio file found in $SCRIPT_DIR_OF_GEN" >&2
  exit 1
fi

echo "Converting: $DRAWIO_FILE"
node "$SCRIPT_DIR/drawio_to_png.mjs" "$DRAWIO_FILE"
