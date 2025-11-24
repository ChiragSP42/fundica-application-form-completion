import json
import boto3
import os
from datetime import datetime
from typing import (
    Any,
    Optional,
    List
)

# Initialize S3 client
s3_client = boto3.client('s3')

# Get environment variables
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

def lambda_handler(event, context):
    """
    This Lambda function is triggered when a user uploads documents.
    It creates metadata.json files for each document in S3.
    """
    
    try:
        # Parse the incoming request
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        username = body.get('username').lower().replace(" ", "_")
        application_form = body.get('applicationForm') # Either CanExport Application form OR <TBD>
        document_count = body.get('documentCount', 0)
        
        # Validate required fields
        if not username or not application_form:
            return error_response(400, 'Missing required fields: username and applicationForm')
        
        if document_count == 0:
            return error_response(400, 'No documents provided')
        
        listy = list_obj_s3(s3_client=s3_client,
                            bucket_name=S3_BUCKET_NAME,
                            folder_name=f'documents/{username}/',
                            delimiter='')
        
        files = [file for file in listy if file.endswith('.pdf') or file.endswith(".docx") or file.endswith(".xlsx")]

        for file in files:
            meta_creation(file)
        
        return success_response({
            'message': 'Metadata created successfully',
            'username': username,
            'documentCount': document_count,
            'nextStep': 'Knowledge base sync will be triggered'
        })
    
    except json.JSONDecodeError as je:
        return error_response(400, f'Invalid JSON in request body: {str(je)}')
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return error_response(500, f'Internal server error: {str(e)}')

def meta_creation(file):
    clientname = file.split("/", 2)[1]
    metadata_key = file + '.metadata.json'
    metadata_content = {
        "metadataAttributes": {
            "username": clientname.replace(" ", "_") # Replace this with username or email
        }
    }

    s3_client.put_object(Bucket=S3_BUCKET_NAME,
                             Key=metadata_key,
                             Body=json.dumps(metadata_content),
                             ContentType='application/json')

def list_obj_s3(s3_client: Any,
                bucket_name: Optional[str],
                folder_name: Optional[str],
                delimiter: Optional[str] = '')-> List[str]:
    """
    Function to return list of objects present in bucket. There is an optional
    delimiter parameter to toggle between folder and file names. If delimiter is empty, 
    it will return all files in the bucket.

    Parameters:
        s3_client (Any): S3 client object
        bucket_name (str): Name of S3 bucket where concerned objects are present.
        foldername (str): Name of folder in which objects are present.
        delimiter (str): Delimiter to toggle between folder and file names. Default is '/'.

    Returns:
        pdf_list (list[str]): List of object names with folder path included.
    """

    obj_list = []
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name,
                                   Prefix=folder_name,
                                   Delimiter=delimiter):
        if delimiter:
            if 'CommonPrefixes' in page:
                obj_list = [obj["Prefix"] for obj in page.get('CommonPrefixes', [])]
        else:
            for obj in page.get('Contents', []):
                key = obj['Key']
                obj_list.append(key)

    return obj_list

def success_response(data):
    """
    Return a successful response with proper CORS headers.
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps(data)
    }

def error_response(status_code, message):
    """
    Return an error response with proper CORS headers.
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': json.dumps({'error': message})
    }
