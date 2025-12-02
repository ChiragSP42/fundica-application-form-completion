import boto3
import os
import json
from typing import Dict

# BOTO3 clients
sfn_client = boto3.client("stepfunctions")

# Environment variables
STATE_MACHINE_ARN = os.getenv("STATE_MACHINE_ARN")

def lambda_handler(event: Dict, context) -> Dict:
    """
    This function get triggered by an S3 event and starts the application form generation orchestration

    Args:
        event (Dict): Payload containing S3 triggered event
        context (_type_): _description_

    Returns:
        Dict: _description_
    """
    if isinstance(event.get("body"), str):
        body = json.loads(event.get("body", {}))
    else:
        body = event.get("body")

    print(body)

    try:
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(body)
        )
        message = {
            "status": "COMPLETED",
            "executionArn": response["executionArn"],
            "startDate": response["startDate"]
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