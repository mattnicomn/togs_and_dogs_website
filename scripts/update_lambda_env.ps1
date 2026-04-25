$FunctionName = "togs-and-dogs-prod-review"
$Profile = "usmissionhero-website-prod"
$SenderEmail = "support@toganddogs.usmissionhero.com"

Write-Host "Fetching current configuration for $FunctionName..."
$ConfigJson = aws lambda get-function-configuration --function-name $FunctionName --profile $Profile --query 'Environment.Variables' --output json

if (-not $ConfigJson) {
    Write-Error "Failed to fetch current configuration. Ensure SSO is logged in."
    return
}

$Config = $ConfigJson | ConvertFrom-Json

# Add or update EMAIL_SENDER
$Vars = @{}
if ($Config -ne $null) {
    $Config.PSObject.Properties | ForEach-Object { $Vars[$_.Name] = $_.Value }
}
$Vars["EMAIL_SENDER"] = $SenderEmail

# Convert back to JSON for CLI
# We need to build the string carefully to avoid quoting issues in the CLI
$VarsDict = @{}
foreach ($key in $Vars.Keys) {
    $VarsDict[$key] = $Vars[$key]
}
$VariablesJson = $VarsDict | ConvertTo-Json -Compress

Write-Host "Updating Lambda with variables: $VariablesJson"

# Escape quotes for command line
$EscapedJson = $VariablesJson.Replace('"', '\"')

aws lambda update-function-configuration --function-name $FunctionName --profile $Profile --environment "Variables=""$EscapedJson"""
