import boto3
import json
import os
from aws_helpers import helpers
from dotenv import load_dotenv
load_dotenv(override=True)

logger = helpers._setup_logger("idk", 10)

aws_access_key = os.getenv('AWS_ACCESS_KEY', None)
aws_secret_key = os.getenv('AWS_SECRET_KEY', None)
s3_client = helpers._get_s3_client(aws_access_key=aws_access_key,
                                   aws_secret_key=aws_secret_key)

listy = helpers.list_obj_s3(s3_client=s3_client,
                            bucket_name='chiggi-testing',
                            folder_name='documents/',
                            delimiter='')
files = [file for file in listy if file.endswith('.pdf') or file.endswith(".docx") or file.endswith(".xlsx")]
metadata_files = [file for file in listy if file.endswith(".metadata.json")]

if len(metadata_files) == 0:
    # No metadata files present, create for all
    for file in files:
        filename, _ = os.path.splitext(os.path.basename(file))
        dirname = os.path.dirname(file)
        clientname = file.split("/", 2)[1]
        metadata_path = os.path.join(dirname, filename)
        metadata_key = metadata_path + '.metadata.json'
        # print(f"File: {file}\nFilename: {filename}\nDirname: {dirname}\nMetadata filename: {metadata_key}\n\n")
        metadata_content = {
            "metadataAttributes": {
                "username": clientname # Replace this with username or email
        }
}
        s3_client.put_object(Bucket='chiggi-testing',
                             Key=metadata_key,
                             Body=json.dumps(metadata_content),
                             ContentType='application/json')
else:
    # logger.debug("Metadata files present")
    # Only create metadata files for those that aren't present
    metadata_file_names = [os.path.basename(file.split(".", 1)[0]) for file in metadata_files]

    for file in files:
        filename, _ = os.path.splitext(os.path.basename(file))
        if filename in metadata_file_names:
            logger.debug(f"Metadata file present for file {filename}")
            clientname = file.split("/", 2)[1]
            dirname = os.path.dirname(file)
            metadata_path = os.path.join(dirname, filename)
            metadata_key = metadata_path + '.metadata.json'
            # logger.debug(f"\nClient name: {clientname}\nFile: {file}\nFilename: {filename}\nDirname: {dirname}\nMetadata filename: {metadata_key}\n\n")
            metadata_content = {
                "metadataAttributes": {
                    "username": clientname # Replace this with username or email
            }
    }
            s3_client.put_object(Bucket='chiggi-testing',
                                Key=metadata_key,
                                Body=json.dumps(metadata_content),
                                ContentType='application/json')