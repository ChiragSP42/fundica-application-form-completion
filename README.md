# Application Form Automation System

> Intelligent document processing and form filling powered by AWS Lambda, Knowledge Bases, and LLMs

## 📋 Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution Architecture](#solution-architecture)
  - [Workflow 1: Template Processing](#workflow-1-template-processing)
  - [Workflow 2: Document Processing & Form Filling](#workflow-2-document-processing--form-filling)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technical Stack](#technical-stack)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Token Management](#token-management)
- [Performance Considerations](#performance-considerations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

---

## Overview

The Application Form Automation System is a POC solution that automates the process of filling out complex application forms by intelligently extracting information from uploaded documents and combining it with templates using AI-powered language models.

The system orchestrates multiple AWS Lambda functions, Knowledge Bases (powered by Bedrock), and LLMs to extract, process, contextualize, and synthesize information to generate completed application forms with minimal manual intervention.

### Key Capabilities

- **Automatic Template Analysis** - Extracts questions and requirements from application form templates
- **Intelligent Document Processing** - Processes client-provided documents and stores them in a searchable Knowledge Base
- **Context-Aware Information Retrieval** - Uses extracted questions to retrieve relevant information from Knowledge Bases
- **Token-Optimized Processing** - Intelligently chunks and processes large documents to respect LLM token limits
- **Concurrent LLM Processing** - Parallelizes form completion across multiple LLM instances for performance
- **Quality Assurance** - Final consolidation and polishing pass ensures coherent, professional output

---

## Problem Statement

Organizations frequently face challenges when dealing with complex application forms:

- **Manual Data Entry** - Information must be manually extracted from multiple documents and entered into forms
- **Time-Consuming** - Form completion can take hours or days for complex applications
- **Error-Prone** - Manual data transfer introduces inconsistencies and errors
- **Scaling Issues** - Difficult to handle multiple forms or large numbers of applications
- **Document Context** - Extracting and matching relevant information from large document sets is labor-intensive

This system solves these challenges by automating the entire pipeline from document upload to completed form delivery.

---

## Solution Architecture

### Workflow 1: Template Processing

**Triggered**: When a new application form template is uploaded to the designated S3 bucket

**Process Flow**:

1. **Lambda Trigger** - S3 upload event triggers initial Lambda function
2. **Template Analysis** - Lambda extracts questions and requirements from the DOCX template
3. **Questions JSON Generation** - Creates `questions.json` containing structured questions extracted from the form
4. **System Prompt Generation** - Copies the master application writing system prompt with the specific form name
5. **Storage** - Stores both artifacts in the same location as template file for later use

**Output Artifacts**:
- `{form_name}_questions.json` - Array of extracted questions used for Knowledge Base queries
- `{form_name}_application_writing_prompt.txt` - Customized system prompt for this specific application form

**Technical Details**:
```
S3 Template Upload
    ↓
Lambda (Template Analyzer)
    ├─ Parse DOCX structure
    ├─ Extract question fields
    ├─ Generate questions.json
    └─ Copy master system prompt
```

---

### Workflow 2: Document Processing & Form Filling

**Triggered**: When client uploads source documents to the input S3 bucket

**Process Flow**:

#### Phase 1: Document Ingestion & Metadata Creation

1. **Document Upload** - Client uploads supporting documents (PDFs, images, etc.) to S3
2. **Lambda Storage** - Initial Lambda stores documents and generates metadata
3. **Metadata Generation** - Creates `metadata.json` containing:
   - Username
   - Year

#### Phase 2: Knowledge Base Synchronization

4. **Lambda Orchestration** - Step Functions triggers synchronization workflow
5. **KB Sync Lambda** - Starts Knowledge Base synchronization job to index uploaded documents
6. **Indexing** - Documents are processed and indexed for semantic search

#### Phase 3: Information Retrieval

7. **Retrieval Lambda** - Uses `questions.json` to query the Knowledge Base
8. **Context Stitching** - Combines all retrieved information into a cohesive text context
9. **Token Counting** - Counts tokens for the combined context

#### Phase 4: Intelligent Chunking (if needed)

10. **Token Limit Check** - Compares total tokens against LLM limit (e.g., 200,000 for Claude Sonnet 4.5)
11. **Content Splitting** - If over limit:
    - Splits content into chunks
    - Repeats token counting for each chunk
    - Continues splitting until all chunks are under limit
12. **Chunk Assignment** - Each chunk is now ready for processing

#### Phase 5: Concurrent LLM Processing

13. **Parallel Execution** - Each chunk is sent concurrently to LLM instances along with:
    - Application form template (DOCX content)
    - Relevant context chunk
    - Specific system prompt
14. **Form Filling** - LLM fills out the form section corresponding to that chunk
15. **Output Collection** - Collects completed form sections from each LLM call

#### Phase 6: Final Consolidation & Polish

16. **Consolidation Lambda** - Merges all form sections into a single document
17. **Final LLM Pass** - Sends consolidated form to a final LLM instance with:
    - Complete filled form sections
    - Master system prompt
    - Instructions to polish and ensure coherence
18. **Output Generation** - Generates final polished, completed form
19. **Delivery** - Returns completed form to client

**Visual Flow**:
```
Document Upload
    ↓
Store & Generate Metadata
    ↓
Sync Knowledge Base
    └─ Index documents
    ↓
Retrieve Information with questions.json
    ↓
Stitch Context Together
    ↓
Count Tokens
    ↓
   [Over Limit?]
    ├─ Yes → Split Content → Recount
    └─ No → Proceed
    ↓
Send to LLMs Concurrently
    ├─ Chunk 1 → LLM 1 → Form Section 1
    ├─ Chunk 2 → LLM 2 → Form Section 2
    └─ Chunk N → LLM N → Form Section N
    ↓
Consolidate Sections
    ↓
Final Polishing LLM Pass
    ↓
Completed Form Output
```

---

## Key Features

### 🤖 Intelligent Processing

- **Semantic Search** - Knowledge Base uses semantic understanding to find relevant information
- **Context Matching** - System prompt guides LLMs to write in appropriate tone and style
- **Coherent Output** - Final pass ensures all sections flow together naturally

### ⚡ Performance Optimized

- **Concurrent Processing** - Parallel LLM calls dramatically reduce total execution time
- **Token-Aware** - Respects LLM token limits with intelligent chunking
- **Efficient Retrieval** - Quick Knowledge Base searches using semantic indexing

### 🔧 Customizable

- **Form-Specific Prompts** - Each form has its own system prompt for tailored writing
- **Configurable Limits** - Token limits adjustable per LLM model

### 📊 Production Ready

- **Error Handling** - Comprehensive error handling and logging throughout
- **Monitoring** - CloudWatch integration for observability
- **Scalability** - Lambda auto-scaling handles variable load
- **State Management** - Step Functions manages complex multi-step workflows

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AWS Environment                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐                    ┌──────────────┐       │
│  │   S3 Bucket  │                    │  S3 Bucket   │       │
│  │  (Templates) │                    │ (Documents)  │       │
│  └──────┬───────┘                    └──────┬───────┘       │
│         │                                   │               │
│         │ Upload                            │ Upload        │
│         ▼                                   ▼               │
│  ┌──────────────────┐            ┌──────────────────┐       │
│  │Template Analysis │            │  Document Intake │       │
│  │Lambda Function   │            │  Lambda Function │       │
│  └──────┬───────────┘            └──────┬───────────┘       │
│         │                               │                   │
│         │ Generates                     │ Generates         │
│         ▼ questions.json                ▼ metadata.json     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         AWS Step Functions Orchestration             │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │ 1. KB Sync Lambda → Sync Knowledge Base        │  │   │
│  │  │ 2. Retrieval Lambda → Query KB + Context       │  │   │
│  │  │ 3. Token Counter → Analyze size & chunk        │  │   │
│  │  │ 4. LLM Pool → Parallel form completion         │  │   │
│  │  │ 5. Consolidator → Merge sections               │  │   │
│  │  │ 6. Final Polish → LLM coherence pass           │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│        │                      │                             │
│        ▼                      ▼                             │
│  ┌──────────────┐      ┌──────────────────┐                 │
│  │  Bedrock KB  │      │  Claude Sonnet   │                 │
│  │  (Semantic   │      │  (Multiple       │                 │
│  │   Search)    │      │   instances)     │                 │
│  └──────────────┘      └──────────────────┘                 │
│         │                      │                            │
│         └──────────┬───────────┘                            │
│                    ▼                                        │
│           ┌─────────────────┐                               │
│           │  S3 Bucket      │                               │
│           │  (Completed     │                               │
│           │   Forms)        │                               │
│           └─────────────────┘                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| Component | Purpose | Trigger |
|-----------|---------|---------|
| **Template Analysis Lambda** | Parses form templates and extracts questions | S3 template upload |
| **Metadata creation Lambda** | Creates metadata | Step Functions |
| **KB Sync Lambda** | Indexes documents in Knowledge Base | Step Functions |
| **Application form completion Lambda** | Fills application form | Step Functions |

---

## Technical Stack

### AWS Services

- **AWS Lambda** - Serverless compute for all processing functions
- **AWS Step Functions** - Workflow orchestration for complex multi-step processes
- **Amazon S3** - Storage for templates, documents, and outputs
- **Amazon Bedrock** - Knowledge Base and LLM access (Claude models)
- **Amazon CloudWatch** - Logging and monitoring

### Languages & Frameworks

- **Python 3.12+** - Primary language for Lambda functions
- **TypeScript** - Infrastructure as Code (AWS CDK)
- **boto3** - AWS SDK for Python

### Key Libraries

- **pypandoc-binary** - DOCX parsing and generation
- **tiktoken** - Token counting for OpenAI models
- **concurrent** - Concurrent request handling
- **json** - Data serialization
- **tempfile** - Temporarily store DOCX file

### LLM Models

- **Claude Sonnet 4.5** - Primary model for form filling (default token limit: 200,000)

---

## Prerequisites

### AWS Account Requirements

- AWS account with appropriate IAM permissions
- Access to AWS Lambda, S3, Step Functions, Bedrock, and CloudWatch
- Bedrock models enabled and foundation model access granted

### Local Development Requirements

- Python 3.12 or higher
- AWS CLI configured with appropriate credentials
- Docker
- AWS CDK CLI (for infrastructure deployment)

### Knowledge Base Setup

- Bedrock Knowledge Base created and configured
- Data source connected (S3 bucket for documents)
- Embeddings model configured and ready

---

## Installation & Setup

### 1. Clone the Repository (Optional if present)

```bash
git clone https://github.com/your-org/application-form-automation.git
cd application-form-automation
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure AWS Credentials

```bash
aws configure
```

Enter the access key and secret key along with the region.

### 5. Deploy Infrastructure

```bash
cd fundica-cdk/infra
cdk deploy
```

This will:
- Create Lambda functions
- Set up S3 buckets
- Configure Step Functions workflow
- Set up IAM roles and policies

### 6. Configure Environment Variables

Create a `.env` file in the infra directory:

```bash
# AWS Configuration
AWS_ACCESS_KEY = your_access_key_id_here
AWS_SECRET_KEY = your_secret_key_here

# Knowledge Base Configuration
KB_DATASOURCE_ID = kb_datasource_id_here
KB_ID = kb_id_here
```

---

## Usage

### Workflow 1: Upload Application Form Template

1. Prepare your application form as a DOCX file
2. Upload to the template bucket via AWS CLI:

```bash
aws s3 cp {application form name}_template.docx s3://fundica-docs-{ACCOUNT ID}/application-forms/{application form name}/{year}/{application form name}_template.docx
```

3. Lambda automatically:
   - Extracts questions
   - Creates `questions.json`
   - Copy pastes master system prompt

### Workflow 2: Upload Documents and Generate Form

1. Prepare supporting documents (PDFs, images, text files)
2. Upload to the document bucket:

```bash
aws s3 cp client_documents/ s3://fundica-users-{ACCOUNT ID}/{username}/{year}/ --recursive
```

3. Trigger application-trigger-lambda to trigger Step Functions workflow
4. Monitor progress in CloudWatch logs and Stepfunction execution:

5. Check output bucket for completed form:

```bash
aws s3 cp s3://fundica-filled-{ACCOUNT ID}/{username}/{year}/ ./ --recursive
```

---

## API Reference

### Lambda Function Inputs/Outputs

#### Application Trigger Lambda

**Input**:

```json
{
  "body": {
    "username": "Client F",
    "year": 2025,
    "applicationFormYear": 2025,
    "applicationForm": "canexport",
    "numResults": 5
  }
}
```

**Output**:

```json
{
    "statusCode": 200,
    "body": {
              "status": "COMPLETED|FAILED",
              "executionArn": "Execution ARN"
            },
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
}
```

#### Metadata Creation Lambda

**Input**:

```python
{
  "body": {
    "username": "Client F",
    "year": 2025,
    "applicationFormYear": 2025,
    "applicationForm": "canexport",
    "numResults": 5
  }
}
```

**Output**:

```python
{
    "statusCode": 200,
    "body": {
            "message": f" {successful} Metadata created successfully and {failed} failed",
            "username": "Client F",
            "applicationForm": "canexport",
            "year": 2025,
            "applicationFormYear": 2025,
            "numResults": 5,
            "nextStep": "Knowledge base sync will be triggered"
        },
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
}
```

#### KB Sync Lambda

**Input**:

```python
{
  "body": {
    "username": "Client F",
    "year": 2025,
    "applicationFormYear": 2025,
    "applicationForm": "canexport",
    "numResults": 5
  }
}
```

**Output**:

```python
{
  "statusCode": 200,
  "body": {
          "message": f" {successful} Metadata created successfully and {failed} failed",
          "username": "Client F",
          "applicationForm": "canexport",
          "year": 2025,
          "applicationFormYear": 2025,
          "numResults": 5
      },
  "headers": {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
  }
}
```

#### Application Form Completion Lambda

**Input**:

```python
{
  "body": {
    "username": "Client F",
    "year": 2025,
    "applicationFormYear": 2025,
    "applicationForm": "canexport",
    "numResults": 5
  }
}
```

**Output**:

```python
{
  "statusCode": 200,
  "body": {
            'message': 'Application form completed',
            'username': username,
            'applicationForm': application_form,
            'generatedAt': f'{date.today()}',
            'filename': f"{username}_{year}_{num_results}_chunks_{application_form}_completed.docx"
          },
  "headers": {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
  }
}
```
---

## Token Management

### Token Counting Strategy

Uses `tiktoken` library

### Efficient Token Usage

Tips to minimize token consumption:

1. **Summarization** - Retrieve summaries before full documents
2. **Targeted Queries** - Use specific questions to retrieve relevant content only
3. **Compression** - Use system prompt to instruct concise completion

---

## Performance Considerations

### Concurrent LLM Calls

The system automatically parallelizes LLM calls based on chunking:

- **Single chunk**: 1 LLM call = 1 calls
- **Two chunks**: 2 LLM calls + 1 final polish call = 3 calls
- **N chunks**: N LLM calls + 1 final polish call = (N+1) calls

Configure max concurrent calls:

```python
MAX_CONCURRENT_CALLS = 5  # Adjust based on rate limits
```

### Execution Timeline

Typical execution times:

| Phase | Duration | Notes |
|-------|----------|-------|
| Document Intake | >1s | Uploading and metadata |
| KB Sync | 1-3s | Depends on document size |
| Retrieval | 2s | Knowledge Base search |
| Token Counting | 1-2s | Per chunk |
| LLM Processing | 80-120s | Per chunk (parallelized) |
| Final Polish | 80-120s | Coherence pass |
| **Total** | **3-8 minutes** | Typical end-to-end |

---

## Troubleshooting

### Common Issues & Solutions

#### Issue: Token Count Exceeds Limit Even After Chunking

**Symptoms**: All content chunks still exceed token limit

**Solutions**:
1. Reduce context by using more specific questions
2. Lower `MAX_CHUNK_SIZE` configuration
3. Use document summarization before processing
4. Enable context deduplication in retrieval

#### Issue: LLM Output Incomplete or Truncated

**Symptoms**: Form sections missing content

**Solutions**:
1. Increase token limit in configuration
2. Reduce token consumption in prompts (be more concise)
3. Check if LLM hit output token limit:

#### Issue: Step Functions Execution Fails

**Symptoms**: Workflow stops with error state

**Solutions**:
1. Check Step Functions execution history:
   ```bash
   aws stepfunctions get-execution-history \
     --execution-arn <execution-arn>
   ```

2. Check individual Lambda function logs
3. Verify IAM permissions for all roles
4. Test individual Lambda functions locally:
   ```bash
   python -m pytest tests/lambda_test.py -v
   ```

#### Issue: Inconsistent Form Output Quality

**Symptoms**: Some sections well-written, others poor

**Solutions**:
1. Improve system prompt - be more specific
2. Add examples to prompt
3. Ensure consistent context quality
4. Test with final polish LLM enabled
5. Use higher-capacity model (Opus vs Sonnet)

**Last Updated**: December 9, 2025

**Maintainers**: Chirag Panchakshari

**Questions?** Contact us at chirag.panchakshari@predictifsolutions.com
