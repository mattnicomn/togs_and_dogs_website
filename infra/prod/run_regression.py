import boto3
import json

session = boto3.Session(profile_name='usmissionhero-website-prod')
lambda_client = session.client('lambda')
dynamo_client = session.resource('dynamodb')
table = dynamo_client.Table('togs-and-dogs-prod-data')

def invoke(func, payload):
    res = lambda_client.invoke(
        FunctionName=func,
        Payload=json.dumps(payload)
    )
    return json.loads(res['Payload'].read())

# Helper to add Admin Context
def invoke_admin(func, payload):
    if "requestContext" not in payload:
        payload["requestContext"] = {
            "authorizer": {
                "claims": {
                    "email": "regression@test.com",
                    "cognito:groups": ["Admin", "Staff"]
                }
            }
        }
    return invoke(func, payload)

print("--- REGRESSION TEST PASS ---")

# 1. Intake
print("1. Testing Intake...")
intake_payload = {
    "body": json.dumps({
        "client_name": "Regression Test",
        "client_email": "regression@test.com",
        "pet_names": "Rover",
        "service_type": "DOG_WALKING",
        "start_date": "2026-06-01",
        "client_id": "client-reg-1"
    })
}
out = invoke("togs-and-dogs-prod-intake", intake_payload)
body = json.loads(out['body'])
req_id = body['request_id']
print(f"   Created REQ#{req_id}. Status: {body['status']}")

# Force status to MEET_GREET_REQUIRED for testing
table.update_item(
    Key={'PK': f"REQ#{req_id}", 'SK': "CLIENT#client-reg-1"},
    UpdateExpression="SET #s = :s",
    ExpressionAttributeNames={'#s': 'status'},
    ExpressionAttributeValues={':s': 'MEET_GREET_REQUIRED'}
)

# 2. Mark M&G Completed
print("2. Testing VERIFY_MEET_GREET...")
verify_payload = {
    "body": json.dumps({
        "request_id": req_id,
        "client_id": "client-reg-1",
        "status": "VERIFY_MEET_GREET"
    })
}
out = invoke_admin("togs-and-dogs-prod-review", verify_payload)
item = table.get_item(Key={'PK': f"REQ#{req_id}", 'SK': "CLIENT#client-reg-1"}).get('Item', {})
print(f"   Post-Verify Status: {item.get('status')}")
if item.get('status') != "READY_FOR_APPROVAL":
    print("   [FAIL] Expected READY_FOR_APPROVAL")

# 3. Approve
print("3. Testing Approve...")
approve_payload = {
    "body": json.dumps({
        "request_id": req_id,
        "client_id": "client-reg-1",
        "status": "APPROVED",
        "reason": "Test"
    })
}
invoke_admin("togs-and-dogs-prod-review", approve_payload)
import time
time.sleep(3) # wait for async job handler
item = table.get_item(Key={'PK': f"REQ#{req_id}", 'SK': "CLIENT#client-reg-1"}).get('Item', {})
job_id = item.get('job_id')
print(f"   Post-Approve Status: {item.get('status')}. Job ID linked: {job_id}")
if not job_id:
    print("   [FAIL] Job ID not linked to request")

# 4. Assign Staff
print("4. Testing Assign Staff...")
assign_payload = {
    "body": json.dumps({
        "job_id": job_id,
        "req_id": req_id,
        "client_id": "client-reg-1",
        "worker_id": "worker-1"
    })
}
out = invoke_admin("togs-and-dogs-prod-assign", assign_payload)
body = json.loads(out['body'])
print(f"   Assign Result Status Code: {out.get('statusCode')}, Msg: {body.get('message')}")
job_item = table.get_item(Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{req_id}"}).get('Item', {})
print(f"   Job Status: {job_item.get('status')}")
if job_item.get('status') != "ASSIGNED":
    print("   [FAIL] Job not ASSIGNED")

# 5. Cancellation
print("5. Testing Cancellation...")
cancel_req_payload = {
    "httpMethod": "POST",
    "path": "/client/cancel",
    "body": json.dumps({
        "request_id": req_id,
        "client_id": "client-reg-1",
        "reason": "Reg test cancel"
    })
}
out = invoke_admin("togs-and-dogs-prod-cancellation", cancel_req_payload)
cancel_deny_payload = {
    "httpMethod": "PUT",
    "path": "/admin/cancel/decision",
    "body": json.dumps({
        "request_id": req_id,
        "client_id": "client-reg-1",
        "decision": "DENY",
        "note": "Not allowed"
    })
}
out2 = invoke_admin("togs-and-dogs-prod-cancellation", cancel_deny_payload)
item = table.get_item(Key={'PK': f"REQ#{req_id}", 'SK': "CLIENT#client-reg-1"}).get('Item', {})
print(f"   Post-Cancel-Deny Status: {item.get('status')}")
if item.get('status') != "CANCELLATION_DENIED":
    print("   [FAIL] Cancellation not denied correctly")

# 6. Archive/Delete
print("6. Testing Archive...")
archive_payload = {
    "httpMethod": "POST",
    "body": json.dumps({
        "PK": f"REQ#{req_id}",
        "SK": "CLIENT#client-reg-1",
        "action": "ARCHIVE"
    })
}
out = invoke_admin("togs-and-dogs-prod-admin", archive_payload)
item = table.get_item(Key={'PK': f"REQ#{req_id}", 'SK': "CLIENT#client-reg-1"}).get('Item', {})
print(f"   Post-Archive Status: {item.get('status')}")
if item.get('status') != "ARCHIVED":
    print("   [FAIL] Archive failed")

# Cleanup
table.delete_item(Key={'PK': f"REQ#{req_id}", 'SK': "CLIENT#client-reg-1"})
if job_id:
    table.delete_item(Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{req_id}"})
pet_id = item.get('pet_id')
if pet_id:
    table.delete_item(Key={'PK': f"PET#{pet_id}", 'SK': "CLIENT#client-reg-1"})

print("--- REGRESSION COMPLETE ---")
