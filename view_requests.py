import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.Session(profile_name='usmissionhero-website-prod').resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('togs-and-dogs-prod-data')

resp = table.scan(
    FilterExpression=Attr('entity_type').eq('REQUEST')
)

for item in resp.get('Items', []):
    print(f"REQ: PK={item['PK']}, SK={item['SK']}, client={item.get('client_name')}, dog={item.get('dog_name')}, status={item.get('status')}")
