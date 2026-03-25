# Build all packages - convenience script

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Building Lambda Layer and Code Packages" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Get build directory
$BUILD_DIR = $PSScriptRoot

# Build layer
Write-Host "STEP 1/2: Building Lambda Layer (dependencies)..." -ForegroundColor Yellow
Write-Host "-----------------------------------------------" -ForegroundColor Yellow
& "$BUILD_DIR\build_layer.ps1"

Write-Host ""
Write-Host ""

# Build code
Write-Host "STEP 2/2: Building Lambda Code Package..." -ForegroundColor Yellow
Write-Host "-----------------------------------------------" -ForegroundColor Yellow
& "$BUILD_DIR\build_code_only.ps1"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "All packages built successfully!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  Code only changed?  Run: .\build\deploy_code.ps1" -ForegroundColor White
Write-Host "  Layer changed?      See build\README.md for layer deploy steps" -ForegroundColor White