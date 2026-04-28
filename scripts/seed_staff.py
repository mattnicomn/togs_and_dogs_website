import boto3
from datetime import datetime

# Configure boto3 with the target profile
session = boto3.Session(profile_name='usmissionhero-website-prod', region_name='us-east-1')
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('togs-and-dogs-prod-data')

staff_members = [
    {
        "PK": "COMPANY#tog_and_dogs",
        "SK": "STAFF#staff_ryan",
        "company_id": "tog_and_dogs",
        "staff_id": "staff_ryan",
        "display_name": "Ryan",
        "role": "owner",
        "is_active": True,
        "is_assignable": True,
        "assignment_color": "var(--staff-ryan)",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    },
    {
        "PK": "COMPANY#tog_and_dogs",
        "SK": "STAFF#staff_wife",
        "company_id": "tog_and_dogs",
        "staff_id": "staff_wife",
        "display_name": "Wife",
        "role": "staff",
        "is_active": True,
        "is_assignable": True,
        "assignment_color": "var(--staff-wife)",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    },
    {
        "PK": "COMPANY#tog_and_dogs",
        "SK": "STAFF#staff_nephew1",
        "company_id": "tog_and_dogs",
        "staff_id": "staff_nephew1",
        "display_name": "Nephew1",
        "role": "staff",
        "is_active": True,
        "is_assignable": True,
        "assignment_color": "var(--staff-nephew1)",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    },
    {
        "PK": "COMPANY#tog_and_dogs",
        "SK": "STAFF#staff_nephew2",
        "company_id": "tog_and_dogs",
        "staff_id": "staff_nephew2",
        "display_name": "Nephew2",
        "role": "staff",
        "is_active": True,
        "is_assignable": True,
        "assignment_color": "var(--staff-nephew2)",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
]

for staff in staff_members:
    print(f"Seeding {staff['display_name']}...")
    table.put_item(Item=staff)

print("Seeding complete.")
