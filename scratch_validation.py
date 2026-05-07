import boto3
import json
import time
import os

os.environ['AWS_PROFILE'] = 'usmissionhero-website-prod'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('togs-and-dogs-prod-data')

request_id = "c352fa8b-7e7d-4f3e-98ac-c2513f745da9"
client_id = "c221b121-4f40-4769-a85f-d1ec179c0eb9"
assign_function = "togs-and-dogs-prod-assign"
review_function = "togs-and-dogs-prod-review"
claims = {
    "email": "admin@toganddogs.com",
    "cognito:groups": "admin",
    "username": "admin-api"
}

def invoke_lambda(func_name, path_params, body):
    payload = {
        "pathParameters": path_params,
        "body": json.dumps(body),
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        }
    }
    response = lambda_client.invoke(
        FunctionName=func_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    return json.loads(response['Payload'].read().decode('utf-8'))

print("2. Assigning to USmissionhero...")
worker_id = "staff_829e01ba"
req = table.get_item(Key={"PK": f"REQ#{request_id}", "SK": f"CLIENT#{client_id}"}).get('Item', {})
job_id = req.get('job_id') or request_id

res = invoke_lambda(assign_function, {"id": request_id}, {
    "job_id": job_id,
    "req_id": request_id,
    "client_id": client_id,
    "worker_id": worker_id,
    "worker_name": "USmissionhero",
    "start_date": "2026-05-20",
    "start_time": "14:00",
    "end_time": "15:00"
})
print("Assign response:", res)

time.sleep(2)

# Check for Google Calendar Event ID
req = table.get_item(Key={"PK": f"REQ#{request_id}", "SK": f"CLIENT#{client_id}"}).get('Item', {})
actual_job_id = req.get('job_id')
print("Request Event ID:", req.get('google_event_id'))

if actual_job_id:
    job = table.get_item(Key={"PK": f"JOB#{actual_job_id}", "SK": f"REQ#{request_id}"}).get('Item', {})
    print("Job Event ID:", job.get('google_event_id'))

    print("\n3. Updating Time (Idempotency Check)...")
    # Update Job manually first
    table.update_item(
        Key={'PK': f"JOB#{actual_job_id}", 'SK': f"REQ#{request_id}"},
        UpdateExpression="SET start_time = :st, end_time = :et",
        ExpressionAttributeValues={":st": "15:00", ":et": "16:00"}
    )
    table.update_item(
        Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
        UpdateExpression="SET start_time = :st, end_time = :et",
        ExpressionAttributeValues={":st": "15:00", ":et": "16:00"}
    )

    res = invoke_lambda(assign_function, {"id": request_id}, {
        "job_id": actual_job_id,
        "req_id": request_id,
        "client_id": client_id,
        "worker_id": worker_id,
        "worker_name": "USmissionhero"
    })
    print("Update assignment response:", res)

    time.sleep(2)
    job = table.get_item(Key={"PK": f"JOB#{actual_job_id}", "SK": f"REQ#{request_id}"}).get('Item', {})
    print("Job Event ID after update:", job.get('google_event_id'))

    print("\n4. Cancelling Request...")
    res = invoke_lambda(review_function, {"id": request_id}, {
        "action": "CANCEL", 
        "reason": "Validation complete",
        "client_id": client_id,
        "status": "CANCELLED",
        "request_id": request_id
    })
    print("Cancel response:", res)

    job = table.get_item(Key={"PK": f"JOB#{actual_job_id}", "SK": f"REQ#{request_id}"}).get('Item', {})
    print("Job Event ID after cancel:", job.get('google_event_id', 'Not Present (Deleted)'))
