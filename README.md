# Docker stuff to manually create lambda function

## Step 1

Create folder called pypandoc-lambda and `cd` into it.

## Step 2

Create requirements.txt with necessary libraries.

```text
pypandoc-binary
boto3
```

## Step 3

Create Dockerfile

```Dockerfile
# Start with AWS's official Python image for Lambda
# This image already has everything Lambda needs
FROM public.ecr.aws/lambda/python:3.13

# Copy your requirements file into the image
# ${LAMBDA_TASK_ROOT} is a special folder inside the container
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install all Python packages listed in requirements.txt
RUN pip install -r requirements.txt

# Copy your Python code into the image
COPY lambda_txt_to_doc.py ${LAMBDA_TASK_ROOT}

# Tell Lambda which function to run
# Format: filename.function_name
CMD [ "<python filename>.,<function name> ]
```

## Step 4

Create lambda function code.

## Step 5

Build docker image.

```bash
docker buildx build --platform linux/amd64 --provenance=false -t pypandoc-lambda:latest .
```

What each flag does:

* --platform linux/amd64: Forces the image to be built for Linux x86_64 architecture (what Lambda uses)​

* --provenance=false: Disables build provenance metadata that creates OCI format (which Lambda doesn't support)​

These are done because AWS Lambda doesn't support the newer OCI image format that recent Docker versions create by default. Lambda only accepts the older Docker v2 manifest format.

This is likely happening because you're on an Apple Silicon Mac (M1/M2/M3) or using a newer Docker version that creates OCI format images

* -t pypandoc-lambda:latest: Tags your image with a name

What happens: Docker reads your Dockerfile line by line and builds the image. You'll see output showing each step. This might take a few minutes the first time.​

When it's done, you'll see: Successfully tagged pypandoc-lambda:latest.

## Step 6

Verify build

```bash
docker images
```

You should see `pypandoc-lambda` with tag latest.

## Step 7

Authenticate Docker with AWS

```bash
aws ecr get-login-password --region YOUR_REGION | \
  docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com
```

What this does: Logs Docker into your AWS account so it can push images.

## Step 8

Creat ECR repository is it doesn't exist

```bash
# This creates a "folder" in AWS to store your image
aws ecr create-repository \
  --repository-name pypandoc-lambda \
  --region YOUR_REGION
```

## Step 9

Tag your image for ECR

```bash
docker tag pypandoc-lambda:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/pypandoc-lambda:latest
```

What this does: Renames your image so AWS knows where to store it

## Step 10

Push to ECR

```bash
# Upload your image to AWS
docker push YOUR_ACCOUNT_ID.dkr.ecr.YOUR_REGION.amazonaws.com/pypandoc-lambda:latest
```

This uploads your image to AWS. It might take a few minutes depending on your internet speed.

## Step 11

Create Lambda Function from Your Image

Using AWS Console:

1. Go to AWS Lambda Console

2. Click "Create function"

3. Select "Container image"​

4. Function name: pypandoc-converter

5. Click "Browse images" button

6. Select your pypandoc-lambda repository

7. Select the latest image tag

8. Click "Create function"​

Configure Function Settings

1. Go to Configuration tab → General configuration

2. Click Edit

3. Set Timeout to 30 seconds (DOCX conversion takes time)

4. Set Memory to 512 MB (Pandoc needs memory)

5. Click Save​

Add S3 Permissions

1. Go to Configuration → Permissions

2. Click on the Role name (opens IAM in new tab)

3. Click Add permissions → Attach policies

4. Search for and select AmazonS3FullAccess (or create custom policy)

5. Click Attach policies

## Step 12: Redeploying code if changes are made

Follow step 5->step 9->step 10

You need to manually go to the function and 'Deploy new image' and choose the image with 'latest' tag.
