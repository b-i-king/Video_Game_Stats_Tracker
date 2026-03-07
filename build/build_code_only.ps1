# Build Lambda code (no dependencies - they're in the layer)

Write-Host "Building Lambda code package..." -ForegroundColor Green

# Set paths (parent of build/ is root)
$ROOT_DIR = Split-Path -Parent $PSScriptRoot
$TEMP_DIR = Join-Path $ROOT_DIR "temp"

# Clean
if (Test-Path "$TEMP_DIR\code_package") { Remove-Item -Recurse -Force "$TEMP_DIR\code_package" }
if (Test-Path "$TEMP_DIR\instagram-poster-code.zip") { Remove-Item -Force "$TEMP_DIR\instagram-poster-code.zip" }

# Create package
New-Item -ItemType Directory -Path "$TEMP_DIR\code_package" -Force | Out-Null

# Copy YOUR code only (from root)
Write-Host "Copying code from project root..." -ForegroundColor Yellow
Copy-Item "$ROOT_DIR\lambda_function.py" "$TEMP_DIR\code_package\"
Copy-Item "$ROOT_DIR\instagram_poster.py" "$TEMP_DIR\code_package\"
Copy-Item -Recurse "$ROOT_DIR\utils" "$TEMP_DIR\code_package\"

# Copy fonts if they exist
if (Test-Path "$ROOT_DIR\fonts") {
    Write-Host "Copying fonts..." -ForegroundColor Yellow
    Copy-Item -Recurse "$ROOT_DIR\fonts" "$TEMP_DIR\code_package\"
}

# Create ZIP
Write-Host "Creating code ZIP..." -ForegroundColor Yellow
Compress-Archive -Path "$TEMP_DIR\code_package\*" -DestinationPath "$TEMP_DIR\instagram-poster-code.zip" -Force

$CodeSize = [math]::Round((Get-Item "$TEMP_DIR\instagram-poster-code.zip").Length / 1MB, 2)

# Calculate unzipped size
$UnzippedSize = (Get-ChildItem -Path "$TEMP_DIR\code_package" -Recurse -File | Measure-Object -Property Length -Sum).Sum
$UnzippedSizeMB = [math]::Round($UnzippedSize / 1MB, 2)

Write-Host ""
Write-Host "SUCCESS: Code package created" -ForegroundColor Green
Write-Host "  Location: temp\instagram-poster-code.zip" -ForegroundColor Cyan
Write-Host "  Compressed: $CodeSize MB" -ForegroundColor Cyan
Write-Host "  Uncompressed: $UnzippedSizeMB MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "This should be under 50MB and much smaller than the layer!" -ForegroundColor Cyan