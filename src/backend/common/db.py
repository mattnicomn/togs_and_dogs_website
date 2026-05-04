import boto3
import os
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get('DATA_TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME) if TABLE_NAME else None

def put_item(item):
    try:
        table.put_item(Item=item)
        return True
    except ClientError as e:
        print(f"Error putting item: {e}")
        return False

def get_item(pk, sk):
    try:
        response = table.get_item(Key={'PK': pk, 'SK': sk})
        return response.get('Item')
    except ClientError as e:
        print(f"Error getting item: {e}")
        return None

def update_status(pk, sk, new_status, audit_note=None, extra_attrs=None):
    """Updates the status and adds to the audit log."""
    try:
        update_expr = "SET #stat = :s"
        expr_attr_names = {"#stat": "status"}
        expr_attr_vals = {":s": new_status}
        
        if extra_attrs:
            for k, v in extra_attrs.items():
                # Avoid collision with #stat
                safe_key = k.replace('-', '_').replace(' ', '_')
                name_key = f"#extra_{safe_key}"
                val_key = f":extra_{safe_key}"
                update_expr += f", {name_key} = {val_key}"
                expr_attr_names[name_key] = k
                expr_attr_vals[val_key] = v

        if audit_note:
            # Simple append to audit log if implemented as a list
            update_expr += ", audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)"
            expr_attr_vals[":n"] = [audit_note]
            expr_attr_vals[":empty_list"] = []

        table.update_item(
            Key={'PK': pk, 'SK': sk},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_vals
        )
        return True
    except ClientError as e:
        print(f"Error updating status: {e}")
        return False

def update_item(pk, sk, attributes):
    """
    Updates multiple attributes on an item.
    attributes: Dictionary of key-value pairs to set.
    """
    try:
        if not attributes:
            return True

        update_expr = "SET "
        expr_attr_names = {}
        expr_attr_vals = {}
        
        parts = []
        for i, (k, v) in enumerate(attributes.items()):
            name_key = f"#n{i}"
            val_key = f":v{i}"
            parts.append(f"{name_key} = {val_key}")
            expr_attr_names[name_key] = k
            expr_attr_vals[val_key] = v
        
        update_expr += ", ".join(parts)
        
        table.update_item(
            Key={'PK': pk, 'SK': sk},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_vals
        )
        return True
    except ClientError as e:
        print(f"Error updating item: {e}")
        return False

def query_by_status(status):
    try:
        response = table.query(
            IndexName='StatusIndex',
            KeyConditionExpression=Key('status').eq(status)
        )
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error querying by status: {e}")
        return []
