import boto3
import json
import os
from aws_helpers import helpers
from dotenv import load_dotenv
load_dotenv(override=True)

"""
Script to create metadata for each file in documents/ if not present. This script will be ported 
and refactored to reside in a lambda function in charge of storing input docs into S3.
"""

logger = helpers._setup_logger("idk", 10)

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY', None)
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY', None)
S3_BUCKET = 'predictif-chiggi-testing'
S3_DOC_FOLER = 'documents/'
s3_client = helpers._get_s3_client(aws_access_key=AWS_ACCESS_KEY,
                                   aws_secret_key=AWS_SECRET_KEY)

def meta_creation(file):
    clientname = file.split("/", 2)[1]
    metadata_key = file + '.metadata.json'
    logger.debug(f"File: {file}\nMetadata filename: {metadata_key}\n\n")
    metadata_content = {
        "metadataAttributes": {
            "username": clientname.replace(" ", "_") # Replace this with username or email
        }
    }

    s3_client.put_object(Bucket=S3_BUCKET,
                             Key=metadata_key,
                             Body=json.dumps(metadata_content),
                             ContentType='application/json')

listy = helpers.list_obj_s3(s3_client=s3_client,
                            bucket_name=S3_BUCKET,
                            folder_name=S3_DOC_FOLER,
                            delimiter='')
files = [file for file in listy if file.endswith('.pdf') or file.endswith(".docx") or file.endswith(".xlsx")]
metadata_files = [file for file in listy if file.endswith(".metadata.json")]

if len(metadata_files) == 0:
    # No metadata files present, create for all
    logger.debug("No metadata files present, create for all\n")
    for file in files:
        meta_creation(file)
else:
    logger.debug("Metadata files present\n")
    # Only create metadata files for those that aren't present
    metadata_file_names = [os.path.basename(file.split(".", 1)[0]) for file in metadata_files]

    for file in files:
        filename, _ = os.path.splitext(os.path.basename(file))
        if filename in metadata_file_names:
            meta_creation(file)