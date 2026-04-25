$ErrorActionPreference = "Stop"

Write-Host "--- REGRESSION TEST PASS ---"

# 1. Intake
Write-Host "1. Testing Intake..."
$intakePayload = @{
    body = '{"client_name": "Regression Test", "client_email": "regression@test.com", "pet_names": "Rover", "service_type": "DOG_WALKING", "start_date": "2026-06-01", "client_id": "client-reg-1"}'
} | ConvertTo-Json -Compress

Set-Content -Path intake_payload.json -Value $intakePayload
aws lambda invoke --function-name togs-and-dogs-prod-intake --payload fileb://intake_payload.json --profile usmissionhero-website-prod out.json | Out-Null
$out = Get-Content out.json | ConvertFrom-Json
$body = $out.body | ConvertFrom-Json
$reqId = $body.request_id
Write-Host "   Created REQ#$reqId. Status: $($body.status)"

# Force status to MEET_GREET_REQUIRED
aws dynamodb update-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --update-expression "SET #stat = :s" --expression-attribute-names "{\`"#stat\`": \`"status\`"}" --expression-attribute-values "{\`":s\`": {\`"S\`": \`"MEET_GREET_REQUIRED\`"}}" --profile usmissionhero-website-prod | Out-Null

# 2. Mark M&G Completed
Write-Host "2. Testing VERIFY_MEET_GREET..."
$verifyPayload = @{
    body = "{\`"request_id\`": \`"$reqId\`", \`"client_id\`": \`"client-reg-1\`", \`"status\`": \`"VERIFY_MEET_GREET\`"}"
} | ConvertTo-Json -Compress

Set-Content -Path verify_payload.json -Value $verifyPayload
aws lambda invoke --function-name togs-and-dogs-prod-review --payload fileb://verify_payload.json --profile usmissionhero-website-prod out.json | Out-Null

$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --profile usmissionhero-website-prod
$item = $itemJson | ConvertFrom-Json
Write-Host "   Post-Verify Status: $($item.Item.status.S)"

# 3. Approve
Write-Host "3. Testing Approve..."
$approvePayload = @{
    body = "{\`"request_id\`": \`"$reqId\`", \`"client_id\`": \`"client-reg-1\`", \`"status\`": \`"APPROVED\`", \`"reason\`": \`"Test\`"}"
} | ConvertTo-Json -Compress

Set-Content -Path approve_payload.json -Value $approvePayload
aws lambda invoke --function-name togs-and-dogs-prod-review --payload fileb://approve_payload.json --profile usmissionhero-website-prod out.json | Out-Null

Start-Sleep -Seconds 3
$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --profile usmissionhero-website-prod
$item = $itemJson | ConvertFrom-Json
$jobId = $item.Item.job_id.S
Write-Host "   Post-Approve Status: $($item.Item.status.S). Job ID linked: $jobId"

# 4. Assign Staff
Write-Host "4. Testing Assign Staff..."
$assignPayload = @{
    body = "{\`"job_id\`": \`"$jobId\`", \`"req_id\`": \`"$reqId\`", \`"worker_id\`": \`"worker-1\`"}"
} | ConvertTo-Json -Compress

Set-Content -Path assign_payload.json -Value $assignPayload
aws lambda invoke --function-name togs-and-dogs-prod-assign --payload fileb://assign_payload.json --profile usmissionhero-website-prod out.json | Out-Null
$out = Get-Content out.json | ConvertFrom-Json
$body = $out.body | ConvertFrom-Json
Write-Host "   Assign Result Status: $($out.statusCode), Msg: $($body.message)"

# 5. Cancellation
Write-Host "5. Testing Cancellation..."
$cancelDenyPayload = @{
    httpMethod = "PUT"
    path = "/admin/cancel/decision"
    body = "{\`"request_id\`": \`"$reqId\`", \`"client_id\`": \`"client-reg-1\`", \`"decision\`": \`"DENY\`", \`"note\`": \`"Not allowed\`"}"
} | ConvertTo-Json -Compress

Set-Content -Path cancel_deny.json -Value $cancelDenyPayload
aws lambda invoke --function-name togs-and-dogs-prod-cancel --payload fileb://cancel_deny.json --profile usmissionhero-website-prod out.json | Out-Null

$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --profile usmissionhero-website-prod
$item = $itemJson | ConvertFrom-Json
Write-Host "   Post-Cancel-Deny Status: $($item.Item.status.S)"

# 6. Archive
Write-Host "6. Testing Archive..."
$archivePayload = @{
    httpMethod = "POST"
    body = "{\`"PK\`": \`"REQ#$reqId\`", \`"SK\`": \`"CLIENT#client-reg-1\`", \`"action\`": \`"ARCHIVE\`"}"
} | ConvertTo-Json -Compress

Set-Content -Path archive_payload.json -Value $archivePayload
aws lambda invoke --function-name togs-and-dogs-prod-admin --payload fileb://archive_payload.json --profile usmissionhero-website-prod out.json | Out-Null

$itemJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --profile usmissionhero-website-prod
$item = $itemJson | ConvertFrom-Json
Write-Host "   Post-Archive Status: $($item.Item.status.S)"

# Cleanup
Write-Host "Cleaning up records..."
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"REQ#$reqId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --profile usmissionhero-website-prod | Out-Null
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"JOB#$jobId\`"}, \`"SK\`": {\`"S\`": \`"REQ#$reqId\`"}}" --profile usmissionhero-website-prod | Out-Null

$petId = $item.Item.pet_id.S
if ($petId) {
    aws dynamodb delete-item --table-name togs-and-dogs-prod-data --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#client-reg-1\`"}}" --profile usmissionhero-website-prod | Out-Null
}
Remove-Item *_payload.json, out.json, cancel_deny.json -ErrorAction SilentlyContinue
Write-Host "--- REGRESSION COMPLETE ---"
