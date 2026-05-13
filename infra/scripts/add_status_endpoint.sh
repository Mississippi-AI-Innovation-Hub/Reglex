#!/bin/bash
# Add GET /v2/query/status/{job_id} endpoint to the existing API Gateway.
# Wires to the same ms-sos-legal-v2 Lambda.

set -e

API_ID="<API_ID>"
V2_ID="4z29e5"  # /v2 resource
REGION="us-east-1"
PROFILE="${AWS_PROFILE:-<your-aws-profile>}"
FUNCTION_NAME="ms-sos-legal-v2"
LAMBDA_ARN="arn:aws:lambda:$REGION:123456789012:function:$FUNCTION_NAME"

echo "=== Adding GET /v2/query/status/{job_id} ==="

# Check if /v2/query/status exists
STATUS_ID=$(aws apigateway get-resources \
    --rest-api-id "$API_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'items[?path==`/v2/query/status`].id' \
    --output text)

# Need to find the /v2/query resource first
QUERY_ID=$(aws apigateway get-resources \
    --rest-api-id "$API_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'items[?path==`/v2/query`].id' \
    --output text)

if [[ -z "$STATUS_ID" || "$STATUS_ID" == "None" ]]; then
    echo "Creating /v2/query/status resource..."
    STATUS_ID=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$QUERY_ID" \
        --path-part "status" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query 'id' \
        --output text)
fi
echo "/v2/query/status resource ID: $STATUS_ID"

# Create /v2/query/status/{job_id}
JOB_ID_RES=$(aws apigateway get-resources \
    --rest-api-id "$API_ID" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --query 'items[?path==`/v2/query/status/{job_id}`].id' \
    --output text)

if [[ -z "$JOB_ID_RES" || "$JOB_ID_RES" == "None" ]]; then
    echo "Creating /v2/query/status/{job_id} resource..."
    JOB_ID_RES=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$STATUS_ID" \
        --path-part "{job_id}" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --query 'id' \
        --output text)
fi
echo "/v2/query/status/{job_id} resource ID: $JOB_ID_RES"

# Add GET method
if ! aws apigateway get-method \
    --rest-api-id "$API_ID" \
    --resource-id "$JOB_ID_RES" \
    --http-method GET \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null 2>&1; then

    echo "Adding GET method..."
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$JOB_ID_RES" \
        --http-method GET \
        --authorization-type "NONE" \
        --request-parameters '{"method.request.path.job_id":true}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$JOB_ID_RES" \
        --http-method GET \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null
fi

# OPTIONS for CORS
if ! aws apigateway get-method \
    --rest-api-id "$API_ID" \
    --resource-id "$JOB_ID_RES" \
    --http-method OPTIONS \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null 2>&1; then

    echo "Adding OPTIONS for CORS..."
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$JOB_ID_RES" \
        --http-method OPTIONS \
        --authorization-type "NONE" \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$JOB_ID_RES" \
        --http-method OPTIONS \
        --type MOCK \
        --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-method-response \
        --rest-api-id "$API_ID" \
        --resource-id "$JOB_ID_RES" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{"method.response.header.Access-Control-Allow-Headers":false,"method.response.header.Access-Control-Allow-Methods":false,"method.response.header.Access-Control-Allow-Origin":false}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null

    aws apigateway put-integration-response \
        --rest-api-id "$API_ID" \
        --resource-id "$JOB_ID_RES" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{"method.response.header.Access-Control-Allow-Headers":"'"'"'Content-Type,Authorization'"'"'","method.response.header.Access-Control-Allow-Methods":"'"'"'GET,OPTIONS'"'"'","method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}' \
        --region "$REGION" \
        --profile "$PROFILE" > /dev/null
fi

# Grant API Gateway permission to invoke Lambda for the status path
STATEMENT_ID="apigateway-v2-status"
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
    --source-arn "arn:aws:execute-api:$REGION:123456789012:$API_ID/*/GET/v2/query/status/*" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null

# Deploy
echo ""
echo "Deploying..."
aws apigateway create-deployment \
    --rest-api-id "$API_ID" \
    --stage-name prod \
    --description "Added status endpoint" \
    --region "$REGION" \
    --profile "$PROFILE" > /dev/null

echo ""
echo "=== Done ==="
echo "Status endpoint: https://$API_ID.execute-api.$REGION.amazonaws.com/prod/v2/query/status/{job_id}"
