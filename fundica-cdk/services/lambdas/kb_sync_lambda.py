import boto3
import os
import json
import time
from datetime import date

KB_ID = os.getenv("KB_ID", '')
KB_DATASOURCE_ID = os.getenv("KB_DATASOURCE_ID", '')

bedrock_agent_client = boto3.client("bedrock-agent")

def lambda_handler(event, context):

    try:
        # Parse the incoming request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        username = body.get('username')
        application_form = body.get('applicationForm').lower() # Either CanExport Application form OR <TBD>
        application_form_year = body.get("applicationFormYear", date.today().year)
        year = body.get('year', date.today().year)
        num_results = body.get('numResults', 5)
        
        # Validate required fields
        if not username or not application_form or not year:
            return error_response(400, 'Missing required fields: username or applicationForm or year')
    
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return error_response(500, f'Internal server error: {str(e)}')

    if check_knowledge_base_exists(bedrock_agent_client=bedrock_agent_client, knowledge_base_name_or_id=KB_ID):
        response = bedrock_agent_client.start_ingestion_job(knowledgeBaseId=KB_ID,
                                                            dataSourceId=KB_DATASOURCE_ID
        )
        ingestion_job_id = response['ingestionJob']['ingestionJobId']

        job_status = ""
        while job_status not in ["COMPLETE", "FAILED", "STOPPED"]:
            job_response = bedrock_agent_client.get_ingestion_job(knowledgeBaseId=KB_ID,
                                                                dataSourceId=KB_DATASOURCE_ID,
                                                                ingestionJobId=ingestion_job_id
            )
            job_status = job_response['ingestionJob']['status']
            print(f"Current job status: {job_status}")
            time.sleep(10)
        
        if job_status == 'COMPLETE':
            return success_response({
            'message': 'Knowledge base ingestion job completed successfully',
            'username': username,
            'applicationForm': application_form,
            'applicationFormYear': application_form_year,
            'year': year,
            'numResults': num_results
        })
        elif job_status == 'FAILED':
            return error_response(message = {
            'message': 'Knowledge base sync failed',
            'username': username,
            'applicationForm': application_form,
            'applicationFormYear': application_form_year,
            'year': year,
            'numResults': num_results
        },
        status_code = 500)
    else:
        return error_response(message = {
            'message': 'Knowledge base does not exist',
            'username': username,
            'applicationForm': application_form,
            'applicationFormYear': application_form_year,
            'year': year,
            'numResults': num_results
        },
        status_code = 400)

def check_knowledge_base_exists(bedrock_agent_client, knowledge_base_name_or_id):
    """
    Checks if a Bedrock knowledge base with the given name or ID exists.

    Args:
        knowledge_base_name_or_id (str): The name or ID of the knowledge base to check.

    Returns:
        bool: True if the knowledge base exists, False otherwise.
    """

    try:
        paginator = bedrock_agent_client.get_paginator('list_knowledge_bases')
        pages = paginator.paginate()

        for page in pages:
            for kb in page.get('knowledgeBaseSummaries', []):
                if kb['name'] == knowledge_base_name_or_id or kb['knowledgeBaseId'] == knowledge_base_name_or_id:
                    return True
        return False
    except Exception as e:
        print(f"Error checking knowledge base: {e}")
        return False
    
def check_data_source_exists(bedrock_agent_client, data_source_name_or_id):
    """
    Checks if a Bedrock data source with the given name or ID exists.

    Args:
        data_source_name_or_id (str): The name or ID of the data source to check.

    Returns:
        bool: True if the data source exists, False otherwise.
    """

    try:
        paginator = bedrock_agent_client.get_paginator('list_data_sources')
        pages = paginator.paginate()

        for page in pages:
            for ds in page.get('dataSourceSummaries', []):
                if ds['name'] == data_source_name_or_id or ds['dataSourceId'] == data_source_name_or_id:
                    return True
        return False
    except Exception as e:
        print(f"Error checking data source: {e}")
        return False
    
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