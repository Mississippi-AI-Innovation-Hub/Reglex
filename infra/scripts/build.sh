#!/bin/bash
# Build Lambda deployment zip for the v2 handler.
#
# Packages lambda_handler.py + opensearch-py + requests-aws4auth
# into a single zip ready for Lambda upload.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
ZIP_FILE="$SCRIPT_DIR/lambda_v2.zip"

echo "=== Building Lambda v2 deployment package ==="

# Clean
rm -rf "$BUILD_DIR"
rm -f "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

# Activate venv
source "$PROJECT_ROOT/venv/bin/activate"

# Install dependencies into build dir with Lambda-compatible platform
echo "Installing dependencies..."
pip install \
    --platform manylinux2014_x86_64 \
    --target "$BUILD_DIR" \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    opensearch-py==2.7.0 \
    requests-aws4auth==1.3.1 \
    urllib3==1.26.20 \
    > /dev/null

# Copy handler
echo "Copying lambda_handler.py..."
cp "$PROJECT_ROOT/lambda_handler.py" "$BUILD_DIR/"

# Remove unnecessary files to reduce zip size
echo "Cleaning up..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true

# Zip it up
echo "Creating zip..."
cd "$BUILD_DIR"
zip -rq "$ZIP_FILE" .
cd -

SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "=== Built $ZIP_FILE ($SIZE) ==="
