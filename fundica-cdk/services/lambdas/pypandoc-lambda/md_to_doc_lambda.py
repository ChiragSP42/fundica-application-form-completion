import json
import boto3
import os
from datetime import date
import pypandoc

S3_FILLED = os.getenv("S3_FILLED")

def lambda_handler(event, context):
    s3_client = boto3.client("s3")
    try:
        # Parse the incoming request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        username = body.get('username')
        application_form = body.get('applicationForm') # Either CanExport Application form OR <TBD>
        filename = body.get('filename')
        year = body.get("year", date.today().year)
        
        # Validate required fields
        if not username:
            return error_response(400, 'Missing required fields: username')
        if not application_form:
            return error_response(400, 'Missing required fields: applicationForm')
    
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return error_response(500, f'Internal server error: {str(e)}')

    text_file = ''
    try:
        response = s3_client.get_object(Bucket=S3_FILLED, Key=f'{username}/{year}/{filename}')
        text_file = response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"md file not found.")
        return error_response(400, f'Application prompt not found at {S3_FILLED}/{username}/{year}/{filename}: {str(e)}')

    temp_docx = '/tmp/output.docx'
    pypandoc.convert_text(
            source=text_file,
            to='docx',
            format='md',
            outputfile=temp_docx
        )
        
        # Upload to S3
    s3_client = boto3.client('s3')
    s3_client.upload_file(temp_docx, S3_FILLED, f'{username}/{year}/{username}_{year}_{application_form}_completed.docx')

    return success_response({
            'message': 'Application form completed',
            'username': username,
            'formType': application_form,
            'generatedAt': f'{date.today()}',
            'filename': f"{date.today()}_{application_form}_completed.txt"
        })

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