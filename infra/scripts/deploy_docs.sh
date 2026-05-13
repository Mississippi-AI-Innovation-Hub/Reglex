#!/bin/bash
# Deploy the updated docs lambda handler that supports Phase 1 + Phase 2 paths.
#
# Updates the existing `ms-sos-get-docs` function with new code and raises timeout.

set -e

FUNCTION_NAME="ms-sos-get-docs"
REGION="us-east-1"
PROFILE="${AWS_PROFILE:-<your-aws-profile>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/docs_build"
ZIP_FILE="$SCRIPT_DIR/docs.zip"

echo "=== Building docs lambda ==="

rm -rf "$BUILD_DIR"
rm -f "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

# Handler file — use name the existing function expects
cp "$PROJECT_ROOT/docs_lamda.py" "$BUILD_DIR/lambda_function.py"

# Rename the handler function from `handler` to `lambda_handler` to match existing config
python3 -c "
with open('$BUILD_DIR/lambda_function.py') as f:
    code = f.read()
code = code.replace('def handler(event, context):', 'def lambda_handler(event, context):')
with open('$BUILD_DIR/lambda_function.py', 'w') as f:
    f.write(code)
"

cd "$BUILD_DIR"
zip -rq "$ZIP_FILE" .
cd -

echo "=== Deploying docs lambda ==="

aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null

echo "Waiting for code update..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --profile "$PROFILE"

# Raise timeout to 15s so multi-path lookups have room
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --timeout 15 \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null

echo "=== Deployed ==="
echo "Test:"
echo "  curl -X POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/docs \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"filename\":\"540-X-22.pdf\",\"state\":\"AL\",\"agency_type\":\"medical\"}'"
