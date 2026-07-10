import pytest
import json
from unittest.mock import patch, MagicMock
from handlers.admin_handler import handler as admin_handler
from handlers.admin_handler import derive_staff_identity_state


def test_derive_staff_identity_state_protected():
    # Profile that is protected (admin@toganddogs.com is in the fallback list)
    profile = {
        "email": "admin@toganddogs.com",
        "cognito_sub": "sub-1"
    }
    res = derive_staff_identity_state(profile, None)
    assert res["identity_state"] == "protected"
    assert res["identity_status_label"] == "Protected"
    assert res["is_protected"] is True
    assert res["is_orphaned_identity"] is False
    assert res["can_manage_identity"] is False
    assert res["identity_warning"] is None


def test_derive_staff_identity_state_profile_only():
    # Profile with no login link
    profile = {
        "email": "staff1@test.com",
        "cognito_sub": "unlinked"
    }
    res = derive_staff_identity_state(profile, None)
    assert res["identity_state"] == "profile_only"
    assert res["identity_status_label"] == "No Login"
    assert res["is_protected"] is False
    assert res["is_orphaned_identity"] is False
    assert res["can_manage_identity"] is True
    assert res["identity_warning"] is None

    # Empty sub
    profile_empty = {
        "email": "staff2@test.com"
    }
    res = derive_staff_identity_state(profile_empty, None)
    assert res["identity_state"] == "profile_only"


def test_derive_staff_identity_state_linked_active():
    profile = {
        "email": "staff@test.com",
        "cognito_sub": "sub-123"
    }
    cog_match = {
        "Username": "staff@test.com",
        "Enabled": True,
        "UserStatus": "CONFIRMED"
    }
    res = derive_staff_identity_state(profile, cog_match)
    assert res["identity_state"] == "linked_active"
    assert res["identity_status_label"] == "Login Active"
    assert res["is_protected"] is False
    assert res["is_orphaned_identity"] is False
    assert res["can_manage_identity"] is True
    assert res["identity_warning"] is None


def test_derive_staff_identity_state_linked_invited():
    profile = {
        "email": "staff@test.com",
        "cognito_sub": "sub-123"
    }
    cog_match = {
        "Username": "staff@test.com",
        "Enabled": True,
        "UserStatus": "FORCE_CHANGE_PASSWORD"
    }
    res = derive_staff_identity_state(profile, cog_match)
    assert res["identity_state"] == "linked_invited"
    assert res["identity_status_label"] == "Invited"
    assert res["is_protected"] is False
    assert res["is_orphaned_identity"] is False
    assert res["can_manage_identity"] is True
    assert res["identity_warning"] is None


def test_derive_staff_identity_state_linked_disabled():
    profile = {
        "email": "staff@test.com",
        "cognito_sub": "sub-123"
    }
    cog_match = {
        "Username": "staff@test.com",
        "Enabled": False,
        "UserStatus": "CONFIRMED"
    }
    res = derive_staff_identity_state(profile, cog_match)
    assert res["identity_state"] == "linked_disabled"
    assert res["identity_status_label"] == "Login Disabled"
    assert res["is_protected"] is False
    assert res["is_orphaned_identity"] is False
    assert res["can_manage_identity"] is True
    assert res["identity_warning"] is None


def test_derive_staff_identity_state_orphaned():
    profile = {
        "email": "staff@test.com",
        "cognito_sub": "sub-missing-123"
    }
    # No cog_match passed
    res = derive_staff_identity_state(profile, None)
    assert res["identity_state"] == "orphaned"
    assert res["identity_status_label"] == "Orphaned Login"
    assert res["is_protected"] is False
    assert res["is_orphaned_identity"] is True
    assert res["can_manage_identity"] is True
    assert res["identity_warning"] == "This profile references a login that no longer exists."


@patch('boto3.client')
@patch('common.db.table')
def test_list_staff_identity_enrichment(mock_table, mock_boto):
    # Mock DynamoDB returning 3 profiles:
    # 1. Protected profile (platform admin)
    # 2. Linked active profile
    # 3. Orphaned profile (cognito_sub set to something but Cognito doesn't have it)
    mock_table.query.return_value = {
        "Items": [
            {
                "PK": "COMPANY#tog_and_dogs",
                "SK": "STAFF#staff_protected",
                "staff_id": "staff_protected",
                "display_name": "Protected Admin",
                "email": "admin@toganddogs.com",
                "cognito_sub": "sub-prot"
            },
            {
                "PK": "COMPANY#tog_and_dogs",
                "SK": "STAFF#staff_active",
                "staff_id": "staff_active",
                "display_name": "Active Sitter",
                "email": "active@test.com",
                "cognito_sub": "sub-active"
            },
            {
                "PK": "COMPANY#tog_and_dogs",
                "SK": "STAFF#staff_orphaned",
                "staff_id": "staff_orphaned",
                "display_name": "Orphaned Profile",
                "email": "orphaned@test.com",
                "cognito_sub": "sub-orphaned"
            }
        ]
    }
    
    # Mock DynamoDB get_item to satisfy require_active_tenant
    def db_get_item_side_effect(Key, **kwargs):
        pk = Key.get("PK")
        sk = Key.get("SK")
        if pk == "TENANT#tog_and_dogs" and sk == "METADATA":
            return {
                "Item": {
                    "PK": "TENANT#tog_and_dogs",
                    "SK": "METADATA",
                    "company_id": "tog_and_dogs",
                    "subscription_status": "active",
                    "subscription_tier": "pro",
                    "is_active": True
                }
            }
        return {}
        
    mock_table.get_item.side_effect = db_get_item_side_effect
    
    # Mock Cognito users response: only returns the active user and protected user
    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    
    mock_client.list_groups.return_value = {
        "Groups": [{"GroupName": "Staff"}, {"GroupName": "Admin"}]
    }
    
    # Match group listings
    def list_users_side_effect(UserPoolId, GroupName):
        if GroupName == "Staff":
            return {
                "Users": [
                    {
                        "Username": "active@test.com",
                        "Enabled": True,
                        "UserStatus": "CONFIRMED",
                        "Attributes": [
                            {"Name": "email", "Value": "active@test.com"},
                            {"Name": "sub", "Value": "sub-active"},
                            {"Name": "custom:company_id", "Value": "tog_and_dogs"}
                        ]
                    }
                ]
            }
        elif GroupName == "Admin":
            return {
                "Users": [
                    {
                        "Username": "admin@toganddogs.com",
                        "Enabled": True,
                        "UserStatus": "CONFIRMED",
                        "Attributes": [
                            {"Name": "email", "Value": "admin@toganddogs.com"},
                            {"Name": "sub", "Value": "sub-prot"},
                            {"Name": "custom:company_id", "Value": "tog_and_dogs"}
                        ]
                    }
                ]
            }
        return {"Users": []}
        
    mock_client.list_users_in_group.side_effect = list_users_side_effect
    
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": "owner@test.com",
                    "sub": "owner-sub",
                    "cognito:groups": "owner",
                    "custom:company_id": "tog_and_dogs"
                }
            }
        },
        "httpMethod": "GET",
        "path": "/admin/staff",
        "pathParameters": {}
    }
    
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    
    staff = body["staff"]
    assert len(staff) == 3
    
    # 1. Protected
    s_prot = next(s for s in staff if s["staff_id"] == "staff_protected")
    assert s_prot["identity_state"] == "protected"
    assert s_prot["identity_status_label"] == "Protected"
    assert s_prot["is_protected"] is True
    assert s_prot["is_orphaned_identity"] is False
    assert s_prot["can_manage_identity"] is False
    
    # 2. Active
    s_active = next(s for s in staff if s["staff_id"] == "staff_active")
    assert s_active["identity_state"] == "linked_active"
    assert s_active["identity_status_label"] == "Login Active"
    assert s_active["is_protected"] is False
    assert s_active["is_orphaned_identity"] is False
    assert s_active["can_manage_identity"] is True
    
    # 3. Orphaned
    s_orph = next(s for s in staff if s["staff_id"] == "staff_orphaned")
    assert s_orph["identity_state"] == "orphaned"
    assert s_orph["identity_status_label"] == "Orphaned Login"
    assert s_orph["is_protected"] is False
    assert s_orph["is_orphaned_identity"] is True
    assert s_orph["can_manage_identity"] is True
    assert s_orph["identity_warning"] == "This profile references a login that no longer exists."
