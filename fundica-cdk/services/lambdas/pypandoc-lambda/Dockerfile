# Start with AWS's official Python image for Lambda
# This image already has everything Lambda needs
FROM public.ecr.aws/lambda/python:3.13

# Copy your requirements file into the image
# ${LAMBDA_TASK_ROOT} is a special folder inside the container
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install all Python packages listed in requirements.txt
RUN pip install -r requirements.txt

# Copy your Python code into the image
COPY md_to_doc_lambda.py ${LAMBDA_TASK_ROOT}

# Tell Lambda which function to run
# Format: filename.function_name
CMD [ "md_to_doc_lambda.lambda_handler" ]
