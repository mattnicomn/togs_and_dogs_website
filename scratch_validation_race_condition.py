import boto3
import json
import time
import os
import threading

os.environ['AWS_PROFILE'] = 'usmissionhero-website-prod'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('togs-and-dogs-prod-data')

request_id = "c352fa8b-7e7d-4f3e-98ac-c2513f745da9"
client_id = "c221b121-4f40-4769-a85f-d1ec179c0eb9"
worker_id = "staff_829e01ba"

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

print("1. Cleaning up previous state...")
invoke_lambda(review_function, {"id": request_id}, {
    "action": "CANCEL", 
    "reason": "Resetting for race condition test",
    "client_id": client_id,
    "status": "CANCELLED",
    "request_id": request_id
})
time.sleep(2)
# Reset to MG_COMPLETED so we can approve it again
table.update_item(
    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
    UpdateExpression="SET #stat = :s, job_id = :jid REMOVE google_event_id",
    ExpressionAttributeNames={"#stat": "status"},
    ExpressionAttributeValues={":s": "MG_COMPLETED", ":jid": ""}
)
print("Request reset to MG_COMPLETED.")

def assign_task():
    print("3. Attempting IMMEDIATE assign to simulate race condition...")
    res = invoke_lambda(assign_function, {"id": request_id}, {
        "job_id": request_id, # UI fallback before reload
        "req_id": request_id,
        "client_id": client_id,
        "worker_id": worker_id,
        "worker_name": "USmissionhero",
        "start_date": "2026-05-20",
        "start_time": "14:00",
        "end_time": "15:00"
    })
    print("Assign response:", res)

print("\n2. Approving Request...")
invoke_lambda(review_function, {"id": request_id}, {
    "action": "APPROVE", 
    "reason": "Validation test",
    "client_id": client_id,
    "status": "APPROVED",
    "request_id": request_id
})

# Fire assign_task immediately without sleep
t = threading.Thread(target=assign_task)
t.start()
t.join()

print("\n4. Waiting for async Job Creation Lambda to finish (simulating time passing)...")
time.sleep(3)

print("5. Checking DB state for orphaned jobs...")
req = table.get_item(Key={"PK": f"REQ#{request_id}", "SK": f"CLIENT#{client_id}"}).get('Item', {})
actual_job_id = req.get('job_id')
print("Request Job ID:", actual_job_id)

from boto3.dynamodb.conditions import Attr
resp = table.scan(FilterExpression=Attr('SK').eq(f"REQ#{request_id}") & Attr('entity_type').eq('JOB'))
print(f"Found {len(resp.get('Items', []))} JOB records for this Request.")
for j in resp.get('Items', []):
    print(" -", j.get('PK'), "Event ID:", j.get('google_event_id'))

print("\n6. Cleaning up test...")
invoke_lambda(review_function, {"id": request_id}, {
    "action": "CANCEL", 
    "reason": "Validation complete",
    "client_id": client_id,
    "status": "CANCELLED",
    "request_id": request_id
})
