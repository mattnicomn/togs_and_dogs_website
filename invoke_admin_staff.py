import boto3
import json

lambda_client = boto3.Session(profile_name='usmissionhero-website-prod').client('lambda', region_name='us-east-1')

event = {
    'httpMethod': 'GET',
    'path': '/admin/staff',
    'requestContext': {
        'authorizer': {
            'claims': {
                'cognito:groups': 'owner',
                'email': 'admin@toganddogs.com'
            }
        }
    }
}

resp = lambda_client.invoke(
    FunctionName='togs-and-dogs-prod-admin',
    InvocationType='RequestResponse',
    Payload=json.dumps(event)
)

result = json.loads(resp['Payload'].read())
print("Response Status Code:", result.get('statusCode'))
print("Response Body:", result.get('body'))
