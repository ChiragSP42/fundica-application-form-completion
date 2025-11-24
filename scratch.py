import boto3
import os
import json 
import pypandoc
from aws_helpers import helpers
from dotenv import load_dotenv
load_dotenv(override=True)

S3_BUCKET_NAME = os.getenv("S3_BUCKET", '')
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", '')
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", '')

session = boto3.Session(aws_access_key_id=AWS_ACCESS_KEY,
                        aws_secret_access_key=AWS_SECRET_KEY,
                        region_name='us-east-1')

s3_client = session.client("s3")

folders = helpers.list_obj_s3(s3_client=s3_client,
                            bucket_name=S3_BUCKET_NAME,
                            folder_name=f"results/",
                            delimiter='/')

for folder in folders:
    files = helpers.list_obj_s3(s3_client=s3_client,
                                bucket_name=S3_BUCKET_NAME,
                                folder_name=folder)
    
    text_files = [file for file in files if file.endswith('.md')]

    for text_file in text_files:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME,
                                                     Key=text_file)
        text_application_form = response['Body'].read().decode('utf-8')
        filename = os.path.basename(text_file).split('.')[0]

        doc_application_form = pypandoc.convert_text(source = text_application_form,
                                                     to='docx',
                                                     format='md',
                                                     outputfile=f'{filename}.docx')
        
        print(f"Converted {text_file}")