$ErrorActionPreference = "Stop"

$petId = "7a9ceca0-1b77-4df6-8809-54848d79cc5f"
$clientId = "a2dd98bb-9549-43c3-9828-912f2c8d2051"

Write-Host "--- BEFORE DYNAMODB STATE (APOLLO) ---"
$beforeJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}"
Write-Host $beforeJson

Write-Host "`nInvoking pet handler to edit Apollo..."
aws lambda invoke --function-name togs-and-dogs-prod-pet --payload fileb://test_apollo_edit.json --profile usmissionhero-website-prod pet_out.json | Out-Null
$outJson = Get-Content pet_out.json
Write-Host "Lambda Response: $outJson"

Write-Host "`n--- AFTER DYNAMODB STATE (APOLLO) ---"
$afterJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}"
Write-Host $afterJson

# Revert name back to "Apollo" to maintain real data integrity
Write-Host "`nReverting Apollo's name..."
aws lambda invoke --function-name togs-and-dogs-prod-pet --payload fileb://test_apollo_revert.json --profile usmissionhero-website-prod pet_out.json | Out-Null

Remove-Item pet_out.json -ErrorAction SilentlyContinue

Write-Host "`n--- REGRESSION TESTS ---"
# Approve -> Job Creation
Set-Content -Path req.json -Value '{"body": "{\"request_id\": \"req-final\", \"client_id\": \"client-final\", \"status\": \"APPROVED\", \"reason\": \"Test\"}"}'
aws dynamodb put-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --item "{\`"PK\`": {\`"S\`": \`"REQ#req-final\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-final\`"}, \`"entity_type\`": {\`"S\`": \`"REQUEST\`"}, \`"status\`": {\`"S\`": \`"READY_FOR_APPROVAL\`"}}" | Out-Null
aws lambda invoke --function-name togs-and-dogs-prod-review --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
Start-Sleep -Seconds 3
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-final\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-final\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
$jobId = $itemJson.Item.job_id.S
Write-Host "Approve -> Job Creation: REQ status is $($itemJson.Item.status.S), Job ID is $jobId"

# Assign Staff
Set-Content -Path req.json -Value '{"body": "{\"job_id\": \"'$jobId'\", \"req_id\": \"req-final\", \"worker_id\": \"worker-1\"}"}'
aws lambda invoke --function-name togs-and-dogs-prod-assign --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$jobItem = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#req-final\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
Write-Host "Assign Staff: Job status is $($jobItem.Item.status.S)"

# Archive
Set-Content -Path req.json -Value '{"httpMethod": "POST", "body": "{\"PK\": \"REQ#req-final\", \"SK\": \"CLIENT#client-final\", \"action\": \"ARCHIVE\"}"}'
aws lambda invoke --function-name togs-and-dogs-prod-admin --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-final\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-final\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
Write-Host "Archive: REQ status is $($itemJson.Item.status.S)"

# Cancel / Deny Cancellation
aws dynamodb update-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-final\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-final\`"}}" --update-expression "SET #s = :s" --expression-attribute-names "{\`"#s\`": \`"status\`"}" --expression-attribute-values "{\`":s\`": {\`"S\`": \`"CANCELLATION_REQUESTED\`"}}" --profile usmissionhero-website-prod | Out-Null

Set-Content -Path req.json -Value '{"httpMethod": "PUT", "path": "/admin/cancel/decision", "body": "{\"request_id\": \"req-final\", \"client_id\": \"client-final\", \"decision\": \"DENY\", \"note\": \"Test Deny\"}"}'
aws lambda invoke --function-name togs-and-dogs-prod-cancellation --payload fileb://req.json --profile usmissionhero-website-prod out.json | Out-Null
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-final\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-final\`"}}" --profile usmissionhero-website-prod | ConvertFrom-Json
Write-Host "Deny Cancellation: REQ status is $($itemJson.Item.status.S)"

# Cleanup
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#req-final\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-final\`"}}" --profile usmissionhero-website-prod | Out-Null
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#req-final\`"}}" --profile usmissionhero-website-prod | Out-Null
Remove-Item req.json, out.json -ErrorAction SilentlyContinue
