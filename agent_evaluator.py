import json
import boto3
from datetime import datetime

# Initialize AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Test cases for security and AWS documentation agent
TEST_CASES = [
    {
        "id": "compliance-1",
        "query": "What are the most common compliance frameworks?",
        "category": "compliance_frameworks",
        "expected_keywords": ["PCI DSS", "NIST", "ISO", "HIPPA"]
    },
    {
        "id": "compliance-2",
        "query": "Tell me about HIPAA compliance",
        "category": "compliance_frameworks",
        "expected_keywords": ["HIPAA", "health", "compliance"]
    },
    {
        "id": "compliance-3",
        "query": "What is PCI DSS?",
        "category": "compliance_frameworks",
        "expected_keywords": ["PCI", "payment", "card"]
    },
    {
        "id": "aws-docs-1",
        "query": "What are AWS Lambda best practices?",
        "category": "aws_documentation",
        "expected_keywords": ["Lambda", "AWS", "best practices"]
    },
    {
        "id": "aws-docs-2",
        "query": "How do I secure an S3 bucket?",
        "category": "aws_documentation",
        "expected_keywords": ["S3", "security", "bucket"]
    },
    {
        "id": "security-news-1",
        "query": "Show me the latest AWS security news",
        "category": "security_news",
        "expected_keywords": ["security", "AWS"]
    },
    {
        "id": "security-news-2",
        "query": "Give me 5 recent security posts",
        "category": "security_news",
        "expected_keywords": ["security"]
    },
    {
        "id": "knowledge-base-1",
        "query": "What information do you have about SHIP?",
        "category": "knowledge_base",
        "expected_keywords": ["Security Health Improvement Program"]
    }
]


def evaluate_response(response_text, expected_keywords):
    """
    Evaluate if the response contains expected keywords.
    Returns a score between 0 and 1.
    """
    response_lower = response_text.lower()
    matches = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
    return matches / len(expected_keywords) if expected_keywords else 0


def run_evaluation(agent_lambda_name, session_id="eval-session"):
    """
    Run all test cases by invoking the production agent Lambda function.
    
    Args:
        agent_lambda_name: Name of the production agent Lambda function
        session_id: Session ID to use for all test invocations
    """
    results = []
    
    # Run each test case
    for case in TEST_CASES:
        test_id = case["id"]
        query = case["query"]
        category = case["category"]
        expected_keywords = case.get("expected_keywords", [])
        
        print(f"Running test: {test_id}")
        
        try:
            # Prepare Lambda invocation payload
            payload = {
                "prompt": query,
                "user": {
                    "session_id": session_id
                }
            }
            
            # Invoke the production agent Lambda
            response = lambda_client.invoke(
                FunctionName=agent_lambda_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            # Parse Lambda response
            response_payload = json.loads(response['Payload'].read())
            
            # Check for Lambda errors
            if response.get('FunctionError'):
                raise Exception(f"Lambda error: {response_payload}")
            
            # Extract agent response
            if response_payload.get('statusCode') == 200:
                response_text = response_payload.get('response', '')
            else:
                raise Exception(f"Agent returned status {response_payload.get('statusCode')}")
            
            # Evaluate response
            score = evaluate_response(response_text, expected_keywords)
            
            # Store result
            results.append({
                "test_id": test_id,
                "category": category,
                "query": query,
                "expected_keywords": expected_keywords,
                "response": response_text,
                "score": score,
                "status": "passed" if score >= 0.5 else "failed",
                "timestamp": datetime.utcnow().isoformat(),
                "lambda_duration_ms": response.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('x-amzn-remapped-content-length')
            })
            
            print(f"Test {test_id}: {'PASSED' if score >= 0.5 else 'FAILED'} (score: {score})")
            
        except Exception as e:
            # Handle errors
            results.append({
                "test_id": test_id,
                "category": category,
                "query": query,
                "expected_keywords": expected_keywords,
                "response": f"ERROR: {str(e)}",
                "score": 0,
                "status": "error",
                "timestamp": datetime.utcnow().isoformat()
            })
            print(f"Test {test_id}: ERROR - {str(e)}")
    
    return results


def generate_summary(results):
    """
    Generate evaluation summary statistics.
    """
    total_tests = len(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["status"] == "error")
    avg_score = sum(r["score"] for r in results) / total_tests if total_tests > 0 else 0
    
    # Category breakdown
    categories = {}
    for result in results:
        cat = result["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "avg_score": 0}
        categories[cat]["total"] += 1
        if result["status"] == "passed":
            categories[cat]["passed"] += 1
        categories[cat]["avg_score"] += result["score"]
    
    for cat in categories:
        categories[cat]["avg_score"] /= categories[cat]["total"]
    
    return {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": passed / total_tests if total_tests > 0 else 0,
        "average_score": avg_score,
        "categories": categories,
        "timestamp": datetime.utcnow().isoformat()
    }


def upload_to_s3(results, summary, bucket_name, prefix="agent-evaluations"):
    """
    Upload evaluation results to S3 bucket.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    
    # Upload detailed results
    results_key = f"{prefix}/results-{timestamp}.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=results_key,
        Body=json.dumps(results, indent=2),
        ContentType='application/json'
    )
    
    # Upload summary
    summary_key = f"{prefix}/summary-{timestamp}.json"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=summary_key,
        Body=json.dumps(summary, indent=2),
        ContentType='application/json'
    )
    
    return {
        "results_s3_uri": f"s3://{bucket_name}/{results_key}",
        "summary_s3_uri": f"s3://{bucket_name}/{summary_key}"
    }


def lambda_handler(event, context):
    """
    Lambda handler for agent evaluation.
    
    Expected event structure:
    {
        "agent_lambda_name": "your-agent-lambda-function-name",
        "s3_bucket": "your-bucket-name",
        "s3_prefix": "agent-evaluations",  # optional
        "session_id": "eval-session-123"   # optional
    }
    """
    # Get required parameters from event
    agent_lambda_name = event.get("agent_lambda_name")
    bucket_name = event.get("s3_bucket")
    
    if not agent_lambda_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required parameter: agent_lambda_name'})
        }
    
    if not bucket_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing required parameter: s3_bucket'})
        }
    
    s3_prefix = event.get("s3_prefix", "agent-evaluations")
    session_id = event.get("session_id", f"eval-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
    
    try:
        # Run evaluation
        print(f"Starting agent evaluation for Lambda: {agent_lambda_name}")
        results = run_evaluation(agent_lambda_name, session_id)
        
        # Generate summary
        print("Generating summary...")
        summary = generate_summary(results)
        
        # Upload to S3
        print(f"Uploading results to S3 bucket: {bucket_name}")
        s3_info = upload_to_s3(results, summary, bucket_name, s3_prefix)
        
        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Evaluation completed successfully',
                'summary': summary,
                's3_locations': s3_info
            }, indent=2)
        }
        
    except Exception as e:
        print(f"Error during evaluation: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

