# Deploy Lambda code package to both functions.
# Always builds a fresh zip first so stale code is never deployed.
#
# Usage (from project root):
#   .\build\deploy_code.ps1
#
# Layer rebuild is separate — only needed when requirements-lambda.txt changes.
# See README.md for layer deploy steps.

$ErrorActionPreference = "Stop"

$BUILD_DIR  = $PSScriptRoot
$ROOT_DIR   = Split-Path -Parent $BUILD_DIR
$REGION     = "us-west-1"
$ZIP_PATH   = "$ROOT_DIR\temp\instagram-poster-code.zip"
$FUNCTIONS  = @("instagram-data-fetcher", "instagram-poster")

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " Lambda Code Deploy" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Fresh build
Write-Host "STEP 1/3: Building fresh code package..." -ForegroundColor Yellow
Write-Host "-----------------------------------------------" -ForegroundColor Yellow
try {
    & "$BUILD_DIR\build_code_only.ps1"
} catch {
    Write-Host "❌ Build failed — aborting deploy." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    exit 1
}

# Confirm zip exists
if (-not (Test-Path $ZIP_PATH)) {
    Write-Host "❌ Zip not found at $ZIP_PATH — aborting." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Deploy to both functions
Write-Host "STEP 2/3: Deploying to Lambda functions..." -ForegroundColor Yellow
Write-Host "-----------------------------------------------" -ForegroundColor Yellow

foreach ($fn in $FUNCTIONS) {
    Write-Host "  Deploying $fn..." -ForegroundColor White
    aws lambda update-function-code `
        --function-name $fn `
        --zip-file "fileb://$ZIP_PATH" `
        --region $REGION `
        --query "CodeSize" `
        --output text | ForEach-Object { Write-Host "    Code size: $_ bytes" -ForegroundColor Gray }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Deploy failed for $fn" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ $fn updated" -ForegroundColor Green
}

Write-Host ""

# Step 3: Wait for both to finish updating
Write-Host "STEP 3/3: Waiting for updates to complete..." -ForegroundColor Yellow
Write-Host "-----------------------------------------------" -ForegroundColor Yellow

foreach ($fn in $FUNCTIONS) {
    Write-Host "  Waiting on $fn..." -ForegroundColor White
    aws lambda wait function-updated `
        --function-name $fn `
        --region $REGION

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ $fn did not reach Active state" -ForegroundColor Red
        exit 1
    }

    $state = aws lambda get-function-configuration `
        --function-name $fn `
        --region $REGION `
        --query "State" `
        --output text

    Write-Host "  ✅ $fn → $state" -ForegroundColor Green
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host " Both functions deployed successfully!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Note: If requirements-lambda.txt changed, rebuild the layer separately." -ForegroundColor DarkYellow
Write-Host "      See build\README.md for layer deploy steps." -ForegroundColor DarkYellow
