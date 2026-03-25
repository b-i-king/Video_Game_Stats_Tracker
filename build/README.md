# Build Scripts

Scripts for building Lambda deployment packages.

## Scripts

- **deploy_code.ps1** - Build fresh zip + deploy both Lambda functions (recommended)
- **build_all.ps1** - Build layer + code zips without deploying
- **build_layer.ps1** - Build Lambda layer (dependencies only)
- **build_code_only.ps1** - Build code package (your files only)

## Usage

### From Project Root
```powershell
# Build fresh zip AND deploy both Lambda functions (most common)
.\build\deploy_code.ps1

# Build zips only (no deploy)
.\build\build_all.ps1
```

### From build/ Directory
```powershell
# You can also run from inside build/
cd build
.\build_all.ps1
```

## What Gets Built

### Layer (Dependencies)
- Location: `temp/lambda-layer.zip`
- Contains: All packages from requirements.txt
- Excludes: boto3, botocore (already in Lambda)
- Size: ~XX MB compressed

### Code (Your Files)
- Location: `temp/instagram-poster-code.zip`
- Contains: lambda_function.py, instagram_poster_main.py, utils/, fonts/
- Size: 2-5 MB compressed

## Script Details

### build_layer.ps1
- Installs dependencies to `temp/layer_package/python/`
- Removes boto3/botocore (redundant)
- Removes tests and .pyc files
- Creates ZIP in correct layer structure

### build_code_only.ps1
- Copies code from project root
- Excludes all dependencies (they're in layer)
- Creates minimal ZIP

### build_all.ps1
- Runs both scripts in sequence
- Shows combined output

## Paths

All scripts are path-aware:
- Reference project root as `$ROOT_DIR`
- Output to `temp/` directory
- Read from project root

## Redeploying Layer and Code in AWS Lambda

**Full Layer Deployment using Powershell**
Type this code in Terminal
```
aws s3 cp temp/lambda-layer.zip s3://YOUR-BUCKET/ --region us-west-1                                                                                                                                                             
$LAYER_ARN = (aws lambda publish-layer-version `
    --layer-name instagram-poster-dependencies `
    --content S3Bucket=YOUR-BUCKET `
    --compatible-runtimes python3.11 `
    --region us-west-1 `
    --query 'LayerVersionArn' `
    --output text)
 
echo $LAYER_ARN
```

**Full Code Deployment using Powershell**
1. Type `aws lambda update-function-code --function-name {YOUR-LAMBDA-FUNCTION-NAME1} --zip-file fileb://temp/instagram-poster-code.zip` in Terminal
2. Type `aws lambda update-function-code --function-name {YOUR-LAMBDA-FUNCTION-NAME2} --zip-file fileb://temp/instagram-poster-code.zip` in Terminal

## Troubleshooting

**Manual AWS Lambda Test**
```
$logB64 = aws lambda invoke `
    --function-name instagram-data-fetcher `
    --payload '{}' `
    --region us-west-1 `
    --log-type Tail `
    --query 'LogResult' `
    --output text `
    --cli-read-timeout 300 `
response.json
```

aws lambda invoke --function-name instagram-data-fetcher --payload '{"MODE": "FETCH"}' --region us-west-1 --log-type Tail --query 'LogResult' --output text --cli-read-timeout 300 response.json    

**Scripts won't run:**
```powershell
# Run from project root, not build/
cd ..
.\build\build_all.ps1
```

**Package too large:**
- Check layer uncompressed size
- May need to remove large dependencies
- Consider optimization strategies