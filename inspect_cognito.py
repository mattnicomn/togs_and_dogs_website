import boto3

cognito = boto3.Session(profile_name='usmissionhero-website-prod').client('cognito-idp', region_name='us-east-1')
user_pool_id = 'us-east-1_counlsXGU'

print("--- All Cognito Users ---")
users_resp = cognito.list_users(UserPoolId=user_pool_id)
for u in users_resp.get('Users', []):
    email = next((a['Value'] for a in u['Attributes'] if a['Name'] == 'email'), 'No Email')
    user_groups = cognito.admin_list_groups_for_user(UserPoolId=user_pool_id, Username=u['Username'])
    grps = [g['GroupName'] for g in user_groups.get('Groups', [])]
    print(f"- Username: {u['Username']}, Email: {email}, Groups: {grps}, Status: {u['UserStatus']}")
