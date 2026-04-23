# Deployment Script for Togs & Dogs Repairs

$profile = "usmissionhero-website-prod"
$lambdas = @("admin", "review", "assign")

# 1. Build and Deploy Backend Lambdas
Push-Location src/backend
foreach ($name in $lambdas) {
    $funcName = "togs-and-dogs-prod-$name"
    Write-Host "Deploying $funcName..."
    
    # Create zip including handlers and common
    if (Test-Path "lambda_$name.zip") { Remove-Item "lambda_$name.zip" }
    
    # Use 7zip or Compress-Archive. Compress-Archive is built-in.
    # We need to include common/* and handlers/{name}_handler.py as handlers/{name}_handler.py
    Compress-Archive -Path "common", "handlers" -DestinationPath "lambda_$name.zip"
    
    aws lambda update-function-code --function-name $funcName --zip-file "fileb://lambda_$name.zip" --profile $profile
}
Pop-Location

# 2. Build and Deploy Frontend
Push-Location web
npm install
npm run build
aws s3 sync dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile $profile
aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile $profile
Pop-Location

Write-Host "Deployment Complete!"
