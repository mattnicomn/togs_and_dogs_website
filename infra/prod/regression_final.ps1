$ErrorActionPreference = "Stop"

$reqId = "req-final"
$clientId = "client-final"

Write-Host "--- RE-STARTING REGRESSION ---"

# Create Client Metadata with M&G complete
Write-Host "Creating Client Metadata..."
aws dynamodb put-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --item "{\`"PK\`": {\`"S\`": \`"CLIENT#$clientId\`"}, \`"SK\`": {\`"S\`": \`"METADATA\`"}, \`"entity_type\`": {\`"S\`": \`"CLIENT\`"}, \`"meet_and_greet_completed\`": {\`"BOOL\`": true}}" | Out-Null

# Re-create the request in READY_FOR_APPROVAL status
Write-Host "Re-creating REQ#$reqId..."
aws dynamodb put-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --item "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}, \`"entity_type\`": {\`"S\`": \`"REQUEST\`"}, \`"status\`": {\`"S\`": \`"READY_FOR_APPROVAL\`"}}" | Out-Null

# 1. Approve -> Job Creation
Write-Host "1. Testing Approve -> Job Creation..."
$approveBody = "{\`"request_id\`": \`"$reqId\`", \`"client_id\`": \`"$clientId\`", \`"status\`": \`"APPROVED\`", \`"reason\`": \`"Final Test\`"}"
$approvePayload = @{ body = $approveBody } | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $approvePayload
aws lambda invoke --function-name togs-and-dogs-prod-review --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null

Start-Sleep -Seconds 5
$item = (aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json).Item
$jobId = $item.job_id.S
Write-Host "   Status: $($item.status.S), Job ID: $jobId"

# 2. Assign Staff
Write-Host "2. Testing Assign Staff..."
$assignBody = "{\`"job_id\`": \`"$jobId\`", \`"req_id\`": \`"$reqId\`", \`"worker_id\`": \`"worker-final\`"}"
$assignPayload = @{ body = $assignBody } | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $assignPayload
aws lambda invoke --function-name togs-and-dogs-prod-assign --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$jobItem = (aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#req-final\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json).Item
Write-Host "   Job Status: $($jobItem.status.S)"

# 3. Archive
Write-Host "3. Testing Archive..."
$archiveBody = "{\`"PK\`": \`"REQ#$reqId\`", \`"SK\`": \`"CLIENT#$clientId\`", \`"action\`": \`"ARCHIVE\`"}"
$archivePayload = @{ httpMethod = "POST"; body = $archiveBody } | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $archivePayload
aws lambda invoke --function-name togs-and-dogs-prod-admin --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$item = (aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json).Item
Write-Host "   Status: $($item.status.S)"

# 4. Deny Cancellation
Write-Host "4. Testing Deny Cancellation..."
aws dynamodb update-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}" --update-expression "SET #s = :s" --expression-attribute-names "{\`"#s\`": \`"status\`"}" --expression-attribute-values "{\`":s\`": {\`"S\`": \`"CANCELLATION_REQUESTED\`"}}" --profile usmissionhero-website-prod | Out-Null

$cancelBody = "{\`"request_id\`": \`"$reqId\`", \`"client_id\`": \`"$clientId\`", \`"decision\`": \`"DENY\`", \`"note\`": \`"Final Deny\`"}"
$cancelPayload = @{ httpMethod = "PUT"; path = "/admin/cancel/decision"; body = $cancelBody } | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $cancelPayload
aws lambda invoke --function-name togs-and-dogs-prod-cancellation --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$item = (aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json).Item
Write-Host "   Status: $($item.status.S)"

# Final Cleanup
Write-Host "Cleaning up..."
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}" --profile usmissionhero-website-prod | Out-Null
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"CLIENT#$clientId\`"}, \`"SK\`": {\`"S\`": \`"METADATA\`"}}" --profile usmissionhero-website-prod | Out-Null
if ($jobId) {
    aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#$reqId\`"}}" --profile usmissionhero-website-prod | Out-Null
}
Remove-Item req.json, out.json -ErrorAction SilentlyContinue

Write-Host "--- REGRESSION COMPLETE ---"
