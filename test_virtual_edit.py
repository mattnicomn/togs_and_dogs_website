import boto3
import json

lambda_client = boto3.Session(profile_name='usmissionhero-website-prod').client('lambda', region_name='us-east-1')

# Target virtual user: cognito_jane_65841e@example.com
event = {
    'httpMethod': 'PATCH',
    'path': '/admin/staff/cognito_jane_65841e@example.com',
    'pathParameters': {
        'staff_id': 'cognito_jane_65841e@example.com'
    },
    'body': json.dumps({
        'is_assignable': True
    }),
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
