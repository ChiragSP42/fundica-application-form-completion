import boto3
import json
import os
from typing import (
    Tuple,
    Dict,
    Optional,
    List
)

# Environement variables
S3_DOCS = os.getenv("S3_DOCS")
MODEL_ID = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'

# Initialize BOTO3 clients
s3_client = boto3.client("s3")
bedrock_runtime_client = boto3.client("bedrock-runtime")

def lambda_handler(event: dict, context):
    try:
        s3_bucket, s3_path, filename = parse_event(event=event)
    except Exception as e:
        print(f"Failed to parse event: {e}")
        message = {
            "status": "FAILED",
            "message": f"Failed to parse event: {e}"
        }
        return return_response(status_code=400, message=message)
    
    # Load application form doc
    response = s3_client.get_object(Bucket=s3_bucket,
                                    Key=s3_path)
    document_bytes = response["Body"].read()

    # Load prompt to create questions.
    response = s3_client.get_object(Bucket=S3_DOCS,
                                    Key=f"prompts/generate_questions_prompt.txt")
    questions_prompt = response["Body"].read().decode('utf-8')

    response = bedrock_runtime_client.converse(modelId=MODEL_ID,
                                               messages=[
                                                   {
                                                       'role': 'user',
                                                       'content': [
                                                           {
                                                               'document': {
                                                                   'format': 'docx',
                                                                   'name': f'{filename}',
                                                                   'source': {
                                                                       'bytes': document_bytes
                                                                   }
                                                               }
                                                           },
                                                       ]
                                                   }
                                               ],
                                               system=[
                                                   {
                                                       'text': questions_prompt
                                                   }
                                               ])
    
    questions = response['output']['message']['content'][0]['text']

    # TODO: Store created questions.json in S3
    # s3_client.put_object(Bucket=s3_bucket,
    #                      Key=)

def parse_event(event: Dict) -> Tuple[str, str, str]:
    """Function to parse event from S3 trigger.

    Args:
        event (str): S3 trigger event message

    Returns:
        Tuple: Tuple of questionnaire S3 bucket name, file path, filename with extension
    """
    body = event.get('Records', [])[0]
    s3_bucket = body['s3']['bucket']['name']

    s3_path = body['s3']['object']['key']
    filename = os.path.basename(s3_path)

    return (s3_bucket, s3_path, filename)

def return_response(status_code: int, message: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(message)
    }