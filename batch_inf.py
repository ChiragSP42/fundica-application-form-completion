from aws_helpers import utils
from aws_helpers import helpers
import os
import uuid
import boto3
from dotenv import load_dotenv
load_dotenv(override=True)

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", None)
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", None)
SYSTEM_PROMPT = "You are filling out a CanExport application form. Answer the questions in the tone of an application form. Just answer the question, with no extra fluff."
S3_BUCKET = 'predictif-chiggi-testing'
FOLDER_NAME = 'batch-inference'
APPLICATION_FORM = 'CanExport'
USER = 'Client_G'
OUTPUT_FOLDER = f'results/'
MODEL_ID = 'us.anthropic.claude-sonnet-4-20250514-v1:0'
# MODEL_ID = 'us.anthropic.claude-3-sonnet-20240229-v1:0'
ROLE_ARN = 'arn:aws:iam::354630286405:role/batch_inference_job_role'

session = boto3.Session(aws_access_key_id=AWS_ACCESS_KEY,
                        aws_secret_access_key=AWS_SECRET_KEY,
                        region_name='us-east-1')

bedrock_agent = session.client('bedrock')
bedrock_runtime_client = session.client('bedrock-runtime')
s3_client = session.client('s3')

batch_inf = utils.BatchInference(bedrock_client=bedrock_agent,
                                 s3_client=s3_client,
                                 bucket_name=S3_BUCKET,
                                 folder_name=FOLDER_NAME,
                                 application_form=APPLICATION_FORM,
                                 user=USER,
                                 output_folder=OUTPUT_FOLDER,
                                 model_id=MODEL_ID,
                                 creation_prompt=SYSTEM_PROMPT,
                                 role_arn=ROLE_ARN,
                                 job_name=f'{uuid.uuid4()}')

# Start batch inference job
# job_id = batch_inf.start_batch_inference_job(new_jsonl=True)

# # Poll for completion
# batch_inf.poll_invocation_job(jobArn=job_id)

# Post processing
response = s3_client.get_object(Bucket=S3_BUCKET, Key=f'{FOLDER_NAME}/{APPLICATION_FORM}/CanExport Application Form.docx')
document_bytes = response['Body'].read()
completed_application = batch_inf.process_batch_inference_output(local_copy=True)
temp = bedrock_runtime_client.converse(modelId=MODEL_ID,
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
                                                        'text': completed_application
                                                    }
                                                ]
                                             }
                                         ],
                                         system=[
                                             {
                                                 'text': 'With reference to the application form docx, rewrite the text that has the relevant information needed to fill the application form'
                                             }
                                         ])
            
with open("final_application_form.txt", "w") as f:
    f.write(temp['output']['message']['content'][0]['text'])