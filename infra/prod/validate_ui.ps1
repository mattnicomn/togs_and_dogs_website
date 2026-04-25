$ErrorActionPreference = "Stop"

$petId = "7a9ceca0-1b77-4df6-8809-54848d79cc5f"
$clientId = "a2dd98bb-9549-43c3-9828-912f2c8d2051"

Write-Host "--- BEFORE DYNAMODB STATE (APOLLO) ---"
$beforeJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}"
Write-Host $beforeJson

Write-Host "`nInvoking pet handler to edit Apollo..."
$payload = @{
    httpMethod = "PUT"
    pathParameters = @{ petId = $petId }
    body = "{\`"PK\`": \`"PET#$petId\`", \`"SK\`": \`"CLIENT#$clientId\`", \`"client_id\`": \`"$clientId\`", \`"pet_id\`": \`"$petId\`", \`"status\`": \`"ACTIVE\`", \`"name\`": \`"Apollo (Edited)\`", \`"entity_type\`": \`"PET\`", \`"created_at\`": \`"2026-04-18T20:25:06.126074\`", \`"meet_and_greet_completed\`": true, \`"health\`": {\`"vet_name\`": \`"Dr. Smith\`", \`"emergency_phone\`": \`"555-0100\`"}, \`"care_instructions\`": \`"Feed twice daily.\`"}"
} | ConvertTo-Json -Compress

Set-Content -Path pet_payload.json -Value $payload
aws lambda invoke --function-name togs-and-dogs-prod-pet --payload fileb://pet_payload.json --profile usmissionhero-website-prod pet_out.json | Out-Null
Get-Content pet_out.json

Write-Host "`n--- AFTER DYNAMODB STATE (APOLLO) ---"
$afterJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}"
Write-Host $afterJson

# Revert name back to "Apollo" to maintain real data integrity
Write-Host "`nReverting Apollo's name..."
$revertPayload = @{
    httpMethod = "PUT"
    pathParameters = @{ petId = $petId }
    body = "{\`"client_id\`": \`"$clientId\`", \`"name\`": \`"Apollo\`", \`"meet_and_greet_completed\`": true}"
} | ConvertTo-Json -Compress
Set-Content -Path pet_payload.json -Value $revertPayload
aws lambda invoke --function-name togs-and-dogs-prod-pet --payload fileb://pet_payload.json --profile usmissionhero-website-prod pet_out.json | Out-Null

Remove-Item pet_payload.json, pet_out.json -ErrorAction SilentlyContinue

Write-Host "`n--- REGRESSION TESTS ---"
# Approve -> Job Creation
$approvePayload = @{
    body = "{\`"request_id\`": \`"req-123\`", \`"client_id\`": \`"client-123\`", \`"status\`": \`"APPROVED\`", \`"reason\`": \`"Test\`"}"
} | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $approvePayload

aws dynamodb put-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --item "{\`"PK\`": {\`"S\`": \`"REQ#req-123\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-123\`"}, \`"entity_type\`": {\`"S\`": \`"REQUEST\`"}, \`"status\`": {\`"S\`": \`"READY_FOR_APPROVAL\`"}}" | Out-Null

aws lambda invoke --function-name togs-and-dogs-prod-review --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
Start-Sleep -Seconds 3
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-123\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-123\`"}}" --profile usmissionhero-website-prod
$item = $itemJson | ConvertFrom-Json
$jobId = $item.Item.job_id.S
Write-Host "Approve -> Job Creation: REQ status is $($item.Item.status.S), Job ID is $jobId"

# Assign Staff
$assignPayload = @{
    body = "{\`"job_id\`": \`"$jobId\`", \`"req_id\`": \`"req-123\`", \`"worker_id\`": \`"worker-1\`"}"
} | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $assignPayload
aws lambda invoke --function-name togs-and-dogs-prod-assign --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$outJson = Get-Content out.json | ConvertFrom-Json
$jobItem = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#req-123\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
Write-Host "Assign Staff: Job status is $($jobItem.Item.status.S)"

# Archive
$archivePayload = @{
    httpMethod = "POST"
    body = "{\`"PK\`": \`"REQ#req-123\`", \`"SK\`": \`"CLIENT#client-123\`", \`"action\`": \`"ARCHIVE\`"}"
} | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $archivePayload
aws lambda invoke --function-name togs-and-dogs-prod-admin --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-123\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-123\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
Write-Host "Archive: REQ status is $($itemJson.Item.status.S)"

# Cancel / Deny Cancellation
aws dynamodb update-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-123\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-123\`"}}" --update-expression "SET #s = :s" --expression-attribute-names "{\`"#s\`": \`"status\`"}" --expression-attribute-values "{\`":s\`": {\`"S\`": \`"CANCELLATION_REQUESTED\`"}}" --profile usmissionhero-website-prod | Out-Null

$cancelPayload = @{
    httpMethod = "PUT"
    path = "/admin/cancel/decision"
    body = "{\`"request_id\`": \`"req-123\`", \`"client_id\`": \`"client-123\`", \`"decision\`": \`"DENY\`", \`"note\`": \`"Test Deny\`"}"
} | ConvertTo-Json -Compress
Set-Content -Path req.json -Value $cancelPayload
aws lambda invoke --function-name togs-and-dogs-prod-cancellation --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-123\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-123\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
Write-Host "Deny Cancellation: REQ status is $($itemJson.Item.status.S)"

# Cleanup
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-123\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-123\`"}}" --profile usmissionhero-website-prod | Out-Null
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#req-123\`"}}" --profile usmissionhero-website-prod | Out-Null
Remove-Item req.json, out.json -ErrorAction SilentlyContinue
