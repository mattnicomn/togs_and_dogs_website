import boto3

dynamodb = boto3.Session(profile_name='usmissionhero-website-prod').resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('togs-and-dogs-prod-data')

print("--- STAFF Records under COMPANY#tog_and_dogs ---")
resp = table.query(
    KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq('COMPANY#tog_and_dogs') & boto3.dynamodb.conditions.Key('SK').begins_with('STAFF#')
)
for item in resp.get('Items', []):
    print(f"- SK: {item['SK']}, Display Name: {item.get('display_name')}, Email: {item.get('email')}, Active: {item.get('is_active')}")

print("\n--- CLIENT Records under COMPANY#tog_and_dogs ---")
resp = table.query(
    KeyConditionExpression=boto3.dynamodb.conditions.Key('PK').eq('COMPANY#tog_and_dogs') & boto3.dynamodb.conditions.Key('SK').begins_with('CLIENT#')
)
for item in resp.get('Items', []):
    print(f"- SK: {item['SK']}, Display Name: {item.get('display_name')}, Email: {item.get('email')}, Active: {item.get('is_active')}")
