#!/bin/bash
# Deploy the Lambda v2 function and wire it to the existing API Gateway.
#
# Creates (or updates) Lambda function `ms-sos-legal-v2`
# Adds a new POST /v2/query endpoint to MS-SOS-CLaRa-API
# Enables CORS for the new endpoint

set -e

FUNCTION_NAME="ms-sos-legal-v2"
REGION="us-east-1"
RUNTIME="python3.11"
HANDLER="lambda_handler.lambda_handler"
ROLE_ARN="arn:aws:iam::123456789012:role/Lambda_Role"
ZIP_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lambda_v2.zip"
TIMEOUT=300
MEMORY=2048

API_ID="<API_ID>"  # MS-SOS-CLaRa-API
ROOT_ID="k2ykmeagu9"

PROFILE="${AWS_PROFILE:-<your-aws-profile>}"

# Environment variables for Lambda
ENV_VARS='{"Variables":{
    "OPENSEARCH_ENDPOINT":"https://search-<your-domain>.<region>.es.amazonaws.com",
    "PHASE1_INDEX":"ms-phase1-legal",
    "PHASE2_INDEX":"multistate-phase2-legal",
    "BEDROCK_MODEL_ID":"mistral.mistral-large-3-675b-instruct",
    "BEDROCK_EMBEDDING_MODEL_ID":"amazon.titan-embed-text-v2:0"
}}'

echo "=== Deploying Lambda v2 ==="

if [[ ! -f "$ZIP_FILE" ]]; then
    echo "ERROR: $ZIP_FILE not found. Run build.sh first."
    exit 1
fi

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --profile "$PROFILE" > /dev/null 2>&1; then
    echo "Function exists — updating code and config..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_FILE" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    echo "Waiting for code update to complete..."
    aws lambda wait function-updated \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --profile "$PROFILE"

    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --handler "$HANDLER" \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --environment "$ENV_VARS" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null
else
    echo "Creating new function $FUNCTION_NAME..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file "fileb://$ZIP_FILE" \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --environment "$ENV_VARS" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    echo "Waiting for function to become active..."
    aws lambda wait function-active \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --profile "$PROFILE"
fi

LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'Configuration.FunctionArn' \
    --output text)

echo "Lambda ARN: $LAMBDA_ARN"

# ── API Gateway wiring ──────────────────────────────────────────────

echo ""
echo "=== Wiring to API Gateway ($API_ID) ==="

# Check if /v2 resource exists, create if not
V2_ID=$(aws apigateway get-resources \
    --rest-api-id "$API_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'items[?path==`/v2`].id' \
    --output text)

if [[ -z "$V2_ID" || "$V2_ID" == "None" ]]; then
    echo "Creating /v2 resource..."
    V2_ID=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$ROOT_ID" \
        --path-part "v2" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query 'id' \
        --output text)
fi
echo "/v2 resource ID: $V2_ID"

# Check if /v2/query exists
QUERY_ID=$(aws apigateway get-resources \
    --rest-api-id "$API_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'items[?path==`/v2/query`].id' \
    --output text)

if [[ -z "$QUERY_ID" || "$QUERY_ID" == "None" ]]; then
    echo "Creating /v2/query resource..."
    QUERY_ID=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$V2_ID" \
        --path-part "query" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query 'id' \
        --output text)
fi
echo "/v2/query resource ID: $QUERY_ID"

# Create POST method + integration if not present
if ! aws apigateway get-method \
    --rest-api-id "$API_ID" \
    --resource-id "$QUERY_ID" \
    --http-method POST \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null 2>&1; then

    echo "Adding POST method..."
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$QUERY_ID" \
        --http-method POST \
        --authorization-type "NONE" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$QUERY_ID" \
        --http-method POST \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null
fi

# Add OPTIONS method for CORS
if ! aws apigateway get-method \
    --rest-api-id "$API_ID" \
    --resource-id "$QUERY_ID" \
    --http-method OPTIONS \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null 2>&1; then

    echo "Adding OPTIONS method for CORS..."
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$QUERY_ID" \
        --http-method OPTIONS \
        --authorization-type "NONE" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$QUERY_ID" \
        --http-method OPTIONS \
        --type MOCK \
        --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-method-response \
        --rest-api-id "$API_ID" \
        --resource-id "$QUERY_ID" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{"method.response.header.Access-Control-Allow-Headers":false,"method.response.header.Access-Control-Allow-Methods":false,"method.response.header.Access-Control-Allow-Origin":false}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-integration-response \
        --rest-api-id "$API_ID" \
        --resource-id "$QUERY_ID" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{"method.response.header.Access-Control-Allow-Headers":"'"'"'Content-Type,Authorization'"'"'","method.response.header.Access-Control-Allow-Methods":"'"'"'POST,OPTIONS'"'"'","method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null
fi

# Grant API Gateway permission to invoke Lambda
STATEMENT_ID="apigateway-v2-query"
aws lambda remove-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "$STATEMENT_ID" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null 2>&1 || true

aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "$STATEMENT_ID" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:123456789012:$API_ID/*/POST/v2/query" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null

# Deploy API
echo ""
echo "Deploying API to 'prod' stage..."
aws apigateway create-deployment \
    --rest-api-id "$API_ID" \
    --stage-name prod \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null

ENDPOINT="https://$API_ID.execute-api.$REGION.amazonaws.com/prod/v2/query"
echo ""
echo "=== Deployment complete ==="
echo ""
echo "Endpoint: $ENDPOINT"
echo ""
echo "Test:"
echo "  curl -X POST $ENDPOINT \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"query\":\"What are dental license fees in Texas?\"}'"
echo ""
echo "Update frontend/.env:"
echo "  VITE_CHAT_ENDPOINT=$ENDPOINT"
