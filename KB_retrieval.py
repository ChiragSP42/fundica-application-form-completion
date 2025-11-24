"""
So the orchestration goes as follows;
Prerequisites:
1. First check if new docs have been synced to knowledge base
Algorithm:
1. Generate answers.
    a. Either ask individual concurrent questions to the model.
    b. Wrap all questions in a JSONL file and send for batch job.
2. Concatenate and/or process answers to get filled form.
3. Convert to docx format.
"""

import boto3
import json
import os
from dotenv import load_dotenv
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError
import time
from threading import Lock
load_dotenv(override=True)

# Initialize client
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", None)
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", None)
S3_BUCKET = os.getenv("S3_BUCKET", None)
APPLICATION_FORM = os.getenv("APPLICATION_FORM", None)
session = boto3.Session(aws_access_key_id=AWS_ACCESS_KEY,
                        aws_secret_access_key=AWS_SECRET_KEY,
                        region_name='us-east-1')
bedrock_agent = session.client('bedrock-agent-runtime')
s3_client = session.client("s3")

# Configuration
KB_ID = os.getenv('KNOWLEDGE_BASE_ID', None)
NUM_RESULTS_PER_QUERY = 10
MAX_WORKERS = 15  # Stay under 20 RPS limit

# Thread-safe counter for progress tracking
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

def retrieve_with_retry(question_text: str, user: str, max_retries: int = 3) -> Dict:
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
                            'equals': {
                                'key': 'username',
                                'value': user
                            }
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
                raise
    
    raise Exception(f"Max retries ({max_retries}) exceeded for question: {question_text}")

def retrieve_context_for_question(question_item: Dict, progress: ProgressTracker, user: str) -> Dict:
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
        response = retrieve_with_retry(question_text, user)
        
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

def retrieve_all_contexts_concurrent(questions: List[Dict], user: str, max_workers: int = 15) -> List[Dict]:
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
            executor.submit(retrieve_context_for_question, q, progress, user): q 
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

# Example Usage
if __name__ == "__main__":
    user = 'Client_F'
    # Load your questions
    with open("improved_questions.json", 'r') as f:
        can_export_questions = json.loads(f.read())
    # can_export_questions = [
    #     {"id": "Q1", "question": "What are the eligibility criteria for the grant?"},
    #     {"id": "Q2", "question": "What is the application deadline?"},
    #     {"id": "Q3", "question": "What documents are required for submission?"},
    #     {"id": "Q4", "question": "What is the maximum funding amount?"},
    #     {"id": "Q5", "question": "How long is the application review process?"},
    #     # Add all your questions here
    # ]
    
    # Retrieve contexts concurrently
    enriched_questions = retrieve_all_contexts_concurrent(
        can_export_questions["questions"], 
        max_workers=MAX_WORKERS,  # Adjust based on your needs,
        user = user
    )
    
    # Save results locally
    with open('enriched_questions.json', 'w') as f:
        json.dump(enriched_questions, f, indent=2)
    # Save results in S3
    try:
        s3_client.put_object(Bucket=S3_BUCKET,
                             Key=f"batch-inference/{APPLICATION_FORM}/{user}/enriched_questions.json",
                             ContentType='application/json',
                             Body=json.dumps(enriched_questions, indent=2))
    except Exception as e:
        print(e)
    
    print(f"Results saved to enriched_questions.json locally and {S3_BUCKET}/batch-inference/{APPLICATION_FORM}/enriched_questions.json")
    
    # Print sample output
    if enriched_questions:
        print(f"\nSample output for {enriched_questions[0]['id']}:")
        print(f"Question: {enriched_questions[0]['question']}")
        print(f"Context length: {len(enriched_questions[0]['context'])} characters")
        print(f"Number of chunks: {enriched_questions[0]['num_chunks']}")
