import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.Session(profile_name='usmissionhero-website-prod').resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('togs-and-dogs-prod-data')

req_id = 'b2d62017-cfaa-437f-91b0-2be880452963'
job_id = 'e7e58463-1eeb-47a6-973c-47bfbe1b8d06'

print("Scanning for job_id or req_id in PK/SK...")
response = table.scan(
    FilterExpression=Attr('PK').contains(job_id) | Attr('SK').contains(job_id) | Attr('job_id').eq(job_id) | Attr('PK').contains(req_id) | Attr('SK').contains(req_id) | Attr('request_id').eq(req_id)
)

for item in response.get('Items', []):
    print(f"Scanned: PK={item['PK']}, SK={item['SK']}, entity_type={item.get('entity_type')}, status={item.get('status')}")

while 'LastEvaluatedKey' in response:
    response = table.scan(
        FilterExpression=Attr('PK').contains(job_id) | Attr('SK').contains(job_id) | Attr('job_id').eq(job_id) | Attr('PK').contains(req_id) | Attr('SK').contains(req_id) | Attr('request_id').eq(req_id),
        ExclusiveStartKey=response['LastEvaluatedKey']
    )
    for item in response.get('Items', []):
        print(f"Scanned: PK={item['PK']}, SK={item['SK']}, entity_type={item.get('entity_type')}, status={item.get('status')}")
