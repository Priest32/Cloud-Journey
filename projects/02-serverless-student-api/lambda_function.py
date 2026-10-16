import json
import os
import uuid

import boto3
from botocore.exceptions import ClientError

table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "Students"))
FIELDS = ["name", "class", "email"]


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def valid(body):
    return all(isinstance(body.get(f), str) and body[f].strip() for f in FIELDS)


def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]
    student_id = (event.get("pathParameters") or {}).get("id")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return respond(400, {"error": "Invalid JSON body"})

    try:
        if method == "POST":
            return create(body)
        if method == "GET" and student_id:
            return get(student_id)
        if method == "PUT" and student_id:
            return update(student_id, body)
        if method == "DELETE" and student_id:
            return delete(student_id)
        return respond(405, {"error": "Method not allowed"})
    except ClientError as e:
        print(e)  # goes to CloudWatch Logs
        return respond(500, {"error": "Internal server error"})


def create(body):
    if not valid(body):
        return respond(400, {"error": "name, class and email are required"})
    item = {"student_id": str(uuid.uuid4())}
    item.update({f: body[f].strip() for f in FIELDS})
    table.put_item(Item=item)
    return respond(201, item)


def get(student_id):
    item = table.get_item(Key={"student_id": student_id}).get("Item")
    if not item:
        return respond(404, {"error": "Student not found"})
    return respond(200, item)


def update(student_id, body):
    if not valid(body):
        return respond(400, {"error": "name, class and email are required"})
    try:
        result = table.update_item(
            Key={"student_id": student_id},
            UpdateExpression="SET #n = :n, #c = :c, #e = :e",
            ExpressionAttributeNames={"#n": "name", "#c": "class", "#e": "email"},
            ExpressionAttributeValues={
                ":n": body["name"].strip(),
                ":c": body["class"].strip(),
                ":e": body["email"].strip(),
            },
            ConditionExpression="attribute_exists(student_id)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(404, {"error": "Student not found"})
        raise
    return respond(200, result["Attributes"])


def delete(student_id):
    try:
        table.delete_item(
            Key={"student_id": student_id},
            ConditionExpression="attribute_exists(student_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(404, {"error": "Student not found"})
        raise
    return respond(200, {"message": "Student deleted"})