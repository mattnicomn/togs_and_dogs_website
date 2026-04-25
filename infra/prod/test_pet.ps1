$ErrorActionPreference = "Stop"

$petId = "pet-legacy-test"
$clientId = "client-123"

Write-Host "Creating legacy pet record..."
# Put an item with a legacy custom attribute "legacy_notes"
aws dynamodb put-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --item "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}, \`"entity_type\`": {\`"S\`": \`"PET\`"}, \`"name\`": {\`"S\`": \`"OldYeller\`"}, \`"age\`": {\`"N\`": \`"10\`"}, \`"legacy_notes\`": {\`"S\`": \`"Do not delete me\`"}}" | Out-Null

Write-Host "`n--- BEFORE DYNAMODB STATE ---"
$beforeJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}"
Write-Host $beforeJson

Write-Host "`nInvoking pet handler to update age to 11..."
$payload = @{
    httpMethod = "PUT"
    pathParameters = @{ petId = $petId }
    body = "{\`"client_id\`": \`"$clientId\`", \`"name\`": \`"OldYeller\`", \`"age\`": 11}"
} | ConvertTo-Json -Compress

Set-Content -Path pet_payload.json -Value $payload
aws lambda invoke --function-name togs-and-dogs-prod-pet --payload fileb://pet_payload.json --profile usmissionhero-website-prod pet_out.json | Out-Null

Write-Host "`n--- AFTER DYNAMODB STATE ---"
$afterJson = aws dynamodb get-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}"
Write-Host $afterJson

# Clean up
aws dynamodb delete-item --table-name togs-and-dogs-prod-data --profile usmissionhero-website-prod --key "{\`"PK\`": {\`"S\`": \`"PET#$petId\`"}, \`"SK\`": {\`"S\`": \`"CLIENT#$clientId\`"}}" | Out-Null
Remove-Item pet_payload.json, pet_out.json -ErrorAction SilentlyContinue
