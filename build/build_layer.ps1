# Build Lambda Layer with dependencies

Write-Host "Building Lambda Layer..." -ForegroundColor Green

# Set paths (parent of build/ is root)
$ROOT_DIR = Split-Path -Parent $PSScriptRoot
$TEMP_DIR = Join-Path $ROOT_DIR "temp"

# Clean
if (Test-Path "$TEMP_DIR\layer_package") { Remove-Item -Recurse -Force "$TEMP_DIR\layer_package" }
if (Test-Path "$TEMP_DIR\lambda-layer.zip") { Remove-Item -Force "$TEMP_DIR\lambda-layer.zip" }

# Create layer structure (MUST be in python/ subdirectory)
New-Item -ItemType Directory -Path "$TEMP_DIR\layer_package\python" -Force | Out-Null

# Install dependencies to layer
Write-Host "Installing dependencies to layer..." -ForegroundColor Yellow
pip install -r "$ROOT_DIR\requirements-lambda.txt" -t "$TEMP_DIR\layer_package\python\" --platform manylinux2014_x86_64 --python-version 3.11 --implementation cp --only-binary=:all:

# Remove boto3/botocore (already in Lambda runtime)
Write-Host "Removing boto3/botocore (already in Lambda)..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$TEMP_DIR\layer_package\python\boto3" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$TEMP_DIR\layer_package\python\botocore" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$TEMP_DIR\layer_package\python\s3transfer" -ErrorAction SilentlyContinue

# Remove .pyc files and __pycache__
Write-Host "Removing compiled files..." -ForegroundColor Yellow
Get-ChildItem -Path "$TEMP_DIR\layer_package\python" -Filter "*.pyc" -Recurse | Remove-Item -Force
Get-ChildItem -Path "$TEMP_DIR\layer_package\python" -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force

# Remove tests
Write-Host "Removing test files..." -ForegroundColor Yellow
Get-ChildItem -Path "$TEMP_DIR\layer_package\python" -Filter "tests" -Recurse -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path "$TEMP_DIR\layer_package\python" -Filter "test_*.py" -Recurse | Remove-Item -Force

# Remove .dist-info metadata (keep only essential)
Write-Host "Cleaning metadata..." -ForegroundColor Yellow
Get-ChildItem -Path "$TEMP_DIR\layer_package\python" -Filter "*.dist-info" -Recurse -Directory | 
    ForEach-Object { 
        Remove-Item "$($_.FullName)\RECORD" -Force -ErrorAction SilentlyContinue
        Remove-Item "$($_.FullName)\INSTALLER" -Force -ErrorAction SilentlyContinue
    }

# Create ZIP
Write-Host "Creating layer ZIP..." -ForegroundColor Yellow
Compress-Archive -Path "$TEMP_DIR\layer_package\*" -DestinationPath "$TEMP_DIR\lambda-layer.zip" -Force

$LayerSize = [math]::Round((Get-Item "$TEMP_DIR\lambda-layer.zip").Length / 1MB, 2)

# Calculate unzipped size
$UnzippedSize = (Get-ChildItem -Path "$TEMP_DIR\layer_package" -Recurse -File | Measure-Object -Property Length -Sum).Sum
$UnzippedSizeMB = [math]::Round($UnzippedSize / 1MB, 2)

Write-Host ""
Write-Host "SUCCESS: Layer created" -ForegroundColor Green
Write-Host "  Location: temp\lambda-layer.zip" -ForegroundColor Cyan
Write-Host "  Compressed: $LayerSize MB" -ForegroundColor Cyan
Write-Host "  Uncompressed: $UnzippedSizeMB MB" -ForegroundColor Cyan

if ($UnzippedSize -gt 262144000) {
    Write-Host "  WARNING: Unzipped size >250MB - may hit Lambda limit!" -ForegroundColor Yellow
}