import json
import boto3
import os
from datetime import date

# Get environment variables
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
SYSTEM_PROMPT = "You are filling out a CanExport application form. Answer the questions in the tone of an application form. Just answer the question, with no extra fluff."
FOLDER_NAME = os.getenv("FOLDER_NAME", None) # batch-inference
APPLICATION_FORM = os.getenv("APPLICATION_FORM", None) # CanExport
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", None) # results/
MODEL_ID = 'us.anthropic.claude-sonnet-4-20250514-v1:0'

# Initialize clients
bedrock_runtime_client = boto3.client("bedrock-runtime")
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    This Lambda function is triggered after the knowledge base sync is complete.
    It generates the completed application form and returns it to the frontend.
    """

    try:
        # Parse the incoming request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        username = body.get('username')
        application_form = body.get('applicationForm') # Either CanExport Application form OR <TBD>
        
        # Validate required fields
        if not username or not application_form:
            return error_response(400, 'Missing required fields: username and applicationForm')
    
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return error_response(500, f'Internal server error: {str(e)}')

    # Read the CanExport Application form in the form of bytes
    print('Read the CanExport Application form in the form of bytes')
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=f'documents/application-forms/{application_form}.docx')
        document_bytes = response['Body'].read()
    except Exception as e:
        print(f"{application_form} not found. Upload applicaiton form first")
        return error_response(400, f'Application form not found: {str(e)}')


    # Load Enriched questions
    print("Load Enriched questions")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=f'documents/application-forms/{application_form}_enriched_questions.json')
        enriched_questions = json.loads(response['Body'].read())
    except Exception as e:
        print(f"{application_form}_enriched_questions.json not found. Check generation of enriched questions.")
        return error_response(400, f'Enriched questions not found: {str(e)}')

    # Load application_writing_prompt.
    print("Load application_writing_prompt.")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=f'prompts/{application_form}_application_writing_prompt.txt')
        application_writing_prompt = json.loads(response['Body'].read())
    except Exception as e:
        print(f"{application_form}_application_writing_prompt.txt not found. Check existence of prompt.")
        return error_response(400, f'Application prompt not found: {str(e)}')

    # Stitch retrieved contents, the questions and the section
    print("Stitch retrieved contents, the questions and the section")
    enriched_data = []
    for enrich in enriched_questions:
        section = enrich['section']
        question = enrich['question']
        context = enrich['context']

        format = f"Section: {section}\nQuestion: {question}\nContext: {context}"
        enriched_data.append(format)

    enriched_text = "\n\n".join(enriched_data)

    # Generate final completed application form
    print("Generate final completed application form")
    try:
        completed_application_form = generate_application_form(document_bytes, enriched_text, application_writing_prompt)
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=f"results/{username}/{date.today()}_{application_form}_completed.text",
                Body=completed_application_form,
                ContentType='text/plain'
            )
        except Exception as s3_error:
            print(f"Warning: Could not save form to S3: {str(s3_error)}")
        return success_response({
            'completedForm': completed_application_form,
            'username': username,
            'formType': application_form,
            'generatedAt': date.today()
        })
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return error_response(500, f'Internal server error: {str(e)}')

def generate_application_form(document_bytes, enriched_text, application_writing_prompt):
    """
    Generate the application form based on the form type.
    This function contains templates for different application types.
    
    Replace the placeholder content with actual data extracted from your knowledge base.
    """

    completed_application_form = bedrock_runtime_client.converse(modelId=MODEL_ID,
                                                messages=[
                                                    {
                                                        'role': 'user',
                                                        'content': [
                                                            {
                                                                'document':{
                                                                    'format': 'docx',
                                                                    'name': 'CanExport Application Form',
                                                                    'source': {
                                                                        'bytes': document_bytes
                                                                    }
                                                                }
                                                            },
                                                            {
                                                                'text': enriched_text
                                                            }
                                                        ]
                                                    }
                                                ],
                                                system=[
                                                    {
                                                        'text': application_writing_prompt
                                                    }
                                                ],
                                                inferenceConfig={
                                                    'maxTokens': 65500
                                                })
    return completed_application_form


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
