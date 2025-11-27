import json
import boto3
import os
import time
import pypandoc
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError
from typing import List, Dict
from botocore.config import Config
from datetime import date
import tiktoken
from io import BytesIO
import tempfile

# Get environment variables
S3_DOCS = os.environ.get('S3_DOCS')
S3_FILLED = os.getenv("S3_FILLED")
KB_ID = os.getenv("KB_ID", '')
NUM_RESULTS_PER_QUERY = 20
MAX_WORKERS = 15
# MODEL_ID = 'us.anthropic.claude-sonnet-4-20250514-v1:0'
# MODEL_ID = 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'
MODEL_ID = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
# COUNTING_MODEL_ID = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0'
# COUNTING_MODEL_ID = 'anthropic.claude-sonnet-4-20250514-v1:0'
COUNTING_MODEL_ID = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'

# Initialize clients
config = Config(
    read_timeout=300,
    connect_timeout=60,
    retries={
        'total_max_attempts': 5,
        'mode': 'adaptive'
    }
)
bedrock_runtime_client = boto3.client("bedrock-runtime", config=config)
bedrock_agent = boto3.client('bedrock-agent-runtime')
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
        year = body.get('year', date.today().year)
        
        # Validate required fields
        if not username or not application_form:
            return return_response(400, {"error": 'Missing required fields: username and applicationForm'})
    
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return return_response(500, {"error": f'Internal server error: {str(e)}'})

    # Read the CanExport Application form in the form of bytes
    print('Read the CanExport Application form template in the form of bytes')
    try:
        response = s3_client.get_object(Bucket=S3_DOCS, Key=f'{application_form}/templates/{application_form}_template.docx')
        document_bytes = response['Body'].read()
    except Exception as e:
        print(f"{application_form} not found. Upload applicaiton form first")
        return return_response(400, {"error": f'Application form template not found: {str(e)}'})


    # Load questions
    print("Load questions")
    try:
        response = s3_client.get_object(Bucket=S3_DOCS, Key=f'{application_form}/questions/{application_form}_questions.json')
        questions = json.loads(response['Body'].read())
    except Exception as e:
        print(f"{application_form}_questions.json not found. Check generation of questions.")
        return return_response(400, {"error": f'Questions not found: {str(e)}'})

    # Create enriched questions concurrently
    print("Create enriched questions")
    enriched_questions = retrieve_all_contexts_concurrent(
        questions["questions"], 
        max_workers=MAX_WORKERS,  # Adjust based on your needs,
        user = username,
        year = year
    )

    # Load application_writing_prompt.
    print("Load application_writing_prompt.")
    try:
        response = s3_client.get_object(Bucket=S3_DOCS, Key=f'{application_form}/prompts/{application_form}_application_writing_prompt.txt')
        application_writing_prompt = response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"{application_form}_application_writing_prompt.txt not found. Check existence of prompt.")
        return return_response(400, {"error": f'Application prompt not found: {str(e)}'})

    # Generate final completed application form
    print("Generate final completed application form")
    try:
        start_time = time.time()
        completed_application_form = generate_application_form(document_bytes, enriched_questions, application_writing_prompt)
        elapsed_time = time.time() - start_time
        print("FORM FILLED!")
        print(f"Total time elapsed: {elapsed_time:.2f} seconds")
        if completed_application_form:
            try:
                # Convert markdown to docx using pypandoc
                print("Converting to docx")
                temp_docx = '/tmp/output.docx'
                pypandoc.convert_text(
                        source=completed_application_form,
                        to='docx',
                        format='md',
                        outputfile=temp_docx
                    )
                print("Uploading to S3")
                s3_client.upload_file(temp_docx, S3_FILLED, f'{username}/{year}/{username}_{year}_{application_form}_completed.docx')

            except Exception as s3_error:
                print(f"Warning: Could not save form to S3: {str(s3_error)}")
                return return_response(400, {"error": f"Warning: Could not save form to S3: {str(s3_error)}"})
            return return_response(200, {
                'message': 'Application form completed',
                'username': username,
                'applicationForm': application_form,
                'generatedAt': f'{date.today()}',
                'filename': f"{username}_{year}_{application_form}_completed.docx"
            })
        else:
            return return_response(400, {"error": f'N+1 approach failed'})
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return return_response(500, {"error": f'Internal server error: {str(e)}'})

def generate_application_form(document_bytes, enriched_questions, application_writing_prompt)-> str:
    """
    Generate the application form based on the form type.
    This function contains templates for different application types.
    
    Replace the placeholder content with actual data extracted from your knowledge base.
    """
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
    # First check if input tokens will fit in one LLM call
    print("First check if input tokens will fit in one LLM call")
    print("Converting to docx")
    with tempfile.NamedTemporaryFile(suffix=".docx") as temp_docx_file:
        temp_docx_file.write(document_bytes)
        temp_docx_file.flush()
        # Use convert_file to convert the temp DOCX file to plain text
        document = pypandoc.convert_file(source_file=temp_docx_file.name, to='plain')
    
    encoding = tiktoken.get_encoding('cl100k_base')
    tokens = len(encoding.encode(document+enriched_text+application_writing_prompt))
    print(f"Total input tokens: {tokens}")
    try:
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
                                                    'maxTokens': 63000
                                                })
        print("Went through in a single call!")
        return completed_application_form['output']['message']['content'][0]['text']
    except bedrock_runtime_client.exceptions.ValidationException as e:
        print(f"Input tokens are too big, implementing (N+1) approach: {e}")
        # Figure out how many concurrent LLM calls are needed
        start_time = time.time()
        filled_parts = split_counter(enriched_questions=enriched_questions,
                      document_bytes=document_bytes,
                      application_writing_prompt=application_writing_prompt)
        if filled_parts:
            # Stitch the part answers and pass it through one final LLM to polish everything out
            stitched = "\n".join(filled_parts)
            print("Final LLM call to polish it out")
            encoding = tiktoken.get_encoding('cl100k_base')
            tokens = len(encoding.encode(document+stitched+"I have attached the application form template. Refer to it and fill out the application form from the context provided"))
            print(f"Total input tokens after everything: {tokens}")
            start_time = time.time()
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
                                                                                        'text': stitched
                                                                                    }
                                                                                ]
                                                                            }
                                                                        ],
                                                                        system=[
                                                                            {
                                                                                'text': "I have attached the application form template. Refer to it and fill out the application form from the context provided"
                                                                            }
                                                                        ],
                                                                        inferenceConfig={
                                                                            'maxTokens': 63000
                                                                        })
            elapsed_time = time.time() - start_time
            print(f"Time elapsed for polishing LLM: {elapsed_time:.2f} seconds")
            return completed_application_form['output']['message']['content'][0]['text']
        else:
            return ""
    
def generate_answers(progress,
                     document_bytes,
                     enriched_text,
                     application_writing_prompt):
    try:
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
                                                                        'maxTokens': 63000
                                                                    })
        
        progress.increment_completed()
        return completed_application_form['output']['message']['content'][0]['text']
    except Exception as e:
        print(f"N + 1 approach failed when generating part answers: {e}")
        progress.increment_failed()
        return ""

def split_counter(enriched_questions: List, 
                  document_bytes, 
                  application_writing_prompt: str) -> List[str]:
    """
    This function determines how many concurrent LLM calls are needed 
    by counting how many splits it takes to pass through the model.

    Args:
        enriched_questions (List): List of dict containing section, question and context
        document_bytes (_type_): The application form template
        application_writing_prompt (str): The system prompt

    Returns:
        int: Number of split
    """
    # Start off with two
    split = 2
    # Flag to detemine when all splits have passed
    split_failed_flag = True
    remainder = 1
    filled_parts = []
    print(f"Total length of enriched questions: {len(enriched_questions)}")
    while split_failed_flag:
        if split >= 3:
            break
        print(f"Split: {split}")
        parts, remainder = divmod(len(enriched_questions), split)
        print(f"Parts: {parts}, Remainder: {remainder}")
        start_index = 0
        # Flag to determine if all splits passed or not
        counting_failed_flag = False
        for i in range(split):
            end_index = start_index + parts + (1 if i<remainder else 0)
            print(f"Start index: {start_index}, End index: {end_index}")
            enriched_quesitions_subset = enriched_questions[start_index: end_index]
            enriched_data = []
            for enrich in enriched_quesitions_subset:
                section = enrich['section']
                question = enrich['question']
                context = enrich['context']

                format = f"Section: {section}\nQuestion: {question}\nContext: {context}"
                enriched_data.append(format)
            enriched_text = "\n\n".join(enriched_data)
            start_index = end_index
            try:
                print("Trying first of many LLM call of split")
                with tempfile.NamedTemporaryFile(suffix=".docx") as temp_docx_file:
                    temp_docx_file.write(document_bytes)
                    temp_docx_file.flush()
                    # Use convert_file to convert the temp DOCX file to plain text
                    document = pypandoc.convert_file(source_file=temp_docx_file.name, to='plain')
                encoding = tiktoken.get_encoding('cl100k_base')
                tokens = len(encoding.encode(document+enriched_text+application_writing_prompt))
                print(f"Total input tokens for first of many LLM: {tokens}")
                start_time = time.time()
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
                                                                        'maxTokens': 20000
                                                                    })
                elapsed_time = time.time() - start_time
                print(f"Time elapsed for first LLM call: {elapsed_time:.2f} seconds")
                print(f"{split} works, proceeding with concurrent LLM calls for rest of it")
                filled_parts.append(completed_application_form['output']['message']['content'][0]['text'])
                max_workers = split if split <= 3 else 3
                counter = i
                progress = ProgressTracker(len(enriched_questions))
                start_time = time.time()
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    end_index = start_index + parts + (1 if counter < remainder else 0)
                    print(f"Start index: {start_index}, End index: {end_index}")
                    enriched_quesitions_subset = enriched_questions[start_index: end_index]
                    enriched_data = []
                    for enrich in enriched_quesitions_subset:
                        section = enrich['section']
                        question = enrich['question']
                        context = enrich['context']

                        format = f"Section: {section}\nQuestion: {question}\nContext: {context}"
                        enriched_data.append(format)
                    enriched_text = "\n\n".join(enriched_data)
                    with tempfile.NamedTemporaryFile(suffix=".docx") as temp_docx_file:
                        temp_docx_file.write(document_bytes)
                        temp_docx_file.flush()
                        # Use convert_file to convert the temp DOCX file to plain text
                        document = pypandoc.convert_file(source_file=temp_docx_file.name, to='plain')
                    encoding = tiktoken.get_encoding('cl100k_base')
                    tokens = len(encoding.encode(document+enriched_text+application_writing_prompt))
                    print(f"Total input tokens for concurrent LLM: {tokens}")
                    start_index = end_index
                    counter += 1
                    future_completed = [executor.submit(generate_answers, 
                                                        progress, 
                                                        document_bytes, 
                                                        enriched_text, 
                                                        application_writing_prompt)]

                    for future in as_completed(future_completed):
                        result = future.result()
                        filled_parts.append(result)

                elapsed_time = time.time() - start_time
                print(f"Time elapsed for concurrent LLM calls: {elapsed_time:.2f} seconds")
                print(f"Average time per split: {(elapsed_time/split):.2f} seconds/split")
                counting_failed_flag = False
                break
            except Exception as e:
                print(f"Split counter failed, incrementing counter: {e}")
                counting_failed_flag = True
                break
            
        if counting_failed_flag == True:
            split += 1
        else:
            split_failed_flag = False
    return filled_parts

class ProgressTracker:
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.lock = Lock()
    
    def increment_completed(self):
        with self.lock:
            self.completed += 1
            print(f"Progress: {self.completed}/{self.total} completed, {self.failed} failed")
    
    def increment_failed(self):
        with self.lock:
            self.failed += 1

def retrieve_with_retry(question_text: str, user: str, year: int, max_retries: int = 3) -> Dict:
    """
    Retrieve from Knowledge Base with exponential backoff retry logic.
    
    Args:
        question_text: The question to retrieve context for
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dict containing retrieval results
    """
    for attempt in range(max_retries):
        try:
            response = bedrock_agent.retrieve(
                knowledgeBaseId=KB_ID,
                retrievalQuery={'text': question_text},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': NUM_RESULTS_PER_QUERY,
                        'filter': {
                            'andAll': [
                                {
                                    'equals': {
                                        'key': 'username',
                                        'value': user
                                    }
                                },
                                {
                                    'equals': {
                                        'key': 'year',
                                        'value': year
                                    }
                                }
                            ]
                        }
                    }
                }
            )
            return response
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ThrottlingException' and attempt < max_retries - 1:
                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + (0.1 * (attempt + 1))
                print(f"Throttled. Waiting {wait_time:.2f}s before retry {attempt + 1}...")
                time.sleep(wait_time)
            else:
                print(f"Error: {e}")
                raise
    
    raise Exception(f"Max retries ({max_retries}) exceeded for question: {question_text}")

def retrieve_context_for_question(question_item: Dict, progress: ProgressTracker, user: str, year: int) -> Dict:
    """
    Retrieve context for a single question with error handling.
    
    Args:
        question_item: Dict with 'id' and 'question' keys
        progress: Progress tracker for monitoring
        
    Returns:
        Dict with question ID, text, context, and metadata
    """
    question_id = question_item['id']
    question_text = question_item['question']
    
    try:
        # Retrieve from Knowledge Base
        response = retrieve_with_retry(question_text, user, year)
        
        # Extract context chunks
        context_chunks = []
        sources = []
        
        for result in response.get('retrievalResults', []):
            content = result.get('content', {})
            if content.get('text'):
                context_chunks.append(content['text'])
                
                # Extract source information
                location = result.get('location', {})
                if location.get('s3Location'):
                    sources.append({
                        'uri': location['s3Location'].get('uri', ''),
                        'score': result.get('score', 0)
                    })
        
        # Combine all chunks
        combined_context = '\n\n---\n\n'.join(context_chunks)
        
        progress.increment_completed()
        
        return {
            'id': question_id,
            'section': question_item['section'],
            'question': question_text,
            'context': combined_context,
            'sources': sources,
            'num_chunks': len(context_chunks),
            'status': 'success'
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR for question {question_id}: {error_msg}")
        
        progress.increment_failed()
        
        return {
            'id': question_id,
            'question': question_text,
            'context': '',
            'error': error_msg,
            'status': 'failed'
        }

def retrieve_all_contexts_concurrent(questions: List[Dict], user: str, year: int, max_workers: int = 15) -> List[Dict]:
    """
    Retrieve contexts for all questions using concurrent threads.
    
    Args:
        questions: List of dicts with 'id' and 'question' keys
        max_workers: Maximum number of concurrent threads (default 15 to stay under 20 RPS)
        
    Returns:
        List of enriched question dicts with retrieved context
    """
    print(f"\n{'='*60}")
    print(f"Starting concurrent retrieval for {len(questions)} questions")
    print(f"Max workers: {max_workers}")
    print(f"Rate limit: 20 requests/second")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    progress = ProgressTracker(len(questions))
    enriched_questions = []
    
    # Use ThreadPoolExecutor for concurrent API calls
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_question = {
            executor.submit(retrieve_context_for_question, q, progress, user, year): q 
            for q in questions
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_question):
            result = future.result()
            enriched_questions.append(result)
    
    # Sort by original question ID to maintain order
    enriched_questions.sort(key=lambda x: x['id'])
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Retrieval Complete!")
    print(f"Total questions: {len(questions)}")
    print(f"Successful: {progress.completed}")
    print(f"Failed: {progress.failed}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print(f"Average time per question: {elapsed_time/len(questions):.2f} seconds")
    print(f"{'='*60}\n")
    
    return enriched_questions

def return_response(status_code: int, message: dict):
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
        'body': json.dumps(message)
    }