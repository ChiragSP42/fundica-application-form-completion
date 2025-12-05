import boto3
import os
import json
from datetime import date
from typing import Optional, Dict

# BOTO3 clients
sfn_client = boto3.client("stepfunctions")

# Environment variables
STATE_MACHINE_ARN = os.getenv("STATE_MACHINE_ARN")

def lambda_handler(event: Dict, context) -> Optional[Dict]:
    """
    This function get triggered by an S3 event and starts the application form generation orchestration

    Args:
        event (Dict): Payload containing S3 triggered event
        context (_type_): _description_

    Returns:
        Dict: _description_
    """

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

        body = {
            'body':{
                'username': username,
                'applicationForm': application_form,
                'applicationFormYear': application_form_year,
                'year': year,
                'numResults': num_results
            }
        }
        
        # Validate required fields
        if not username or not application_form or not year:
            message = {
            "status": "FAILED",
            "error": f"Missing required fields: username or applicationForm or year"
            }
            return return_response(400, message=message)
    
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        message = {
            "status": "FAILED",
            "error": f"Internal server error: {str(e)}"
        }
        return return_response(400, message=message)

    print(f"Body: {body}")
    try:
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(body)
        )
        message = {
            "status": "COMPLETED",
            "executionArn": response["executionArn"]
        }
        return return_response(200, message=message)
    except Exception as e:
        message = {
            "status": "FAILED",
            "error": f"State machine execution failed: {str(e)}"
        }
        return return_response(400, message=message)


def return_response(status_code: int, message: dict):
    return {
        "statusCode": status_code,
        "body": json.dumps(message),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    }