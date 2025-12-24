import json
import jsonschema
import os
import boto3
import uuid
import logging
from passlib.hash import pbkdf2_sha256

from datetime import datetime
from jsonschema import validate
from Constants import (
    USER_TYPE_ADMIN, 
    USER_TYPE_ACCOUNTING, 
    USER_TYPE_CUSTOMER,
    USER_STATUS_ACTIVE,
    USER_STATUS_PENDING_CONFIRMATION
)

# # Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

from Utils import get_response

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(f"users-table-{os.environ.get('ENVIRONMENT')}")
company_table = dynamodb.Table(f"companies-table-{os.environ.get('ENVIRONMENT')}")

def load_schema():
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.json')
    with open(schema_path, 'r') as f:
        return json.load(f)

def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)

def get_user_type_from_authorizer(event):
    try:
        authorizer = event.get('requestContext', {}).get('authorizer', {})
        authorizer_type = authorizer.get('type')
        
        if not authorizer_type:
            raise ValueError("User type not found in authorizer context")
            
        if authorizer_type == USER_TYPE_ADMIN:
            return USER_TYPE_ACCOUNTING 
        elif authorizer_type == USER_TYPE_ACCOUNTING:
            return USER_TYPE_CUSTOMER
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error getting user type from authorizer: {str(e)}")
        raise

def validate_company_id(company_id, user_type):
    validate_company_id_response = {
        "error": None,
        "valid": True
    }

    response = company_table.get_item(
        Key={'id': company_id}
    )

    logger.info(f"Company response: {response}")

    if 'Item' not in response:
        validate_company_id_response['valid'] = False
        validate_company_id_response['error'] = "Company not found"
        validate_company_id_response['status_code'] = 404
    else:
        if response['Item']['active'] == False:
            validate_company_id_response['valid'] = False
            validate_company_id_response['error'] = "Company is not active"
            validate_company_id_response['status_code'] = 403

        if response['Item']['type'] != user_type:
            validate_company_id_response['valid'] = False
            validate_company_id_response['error'] = "Company type is not valid"
            validate_company_id_response['status_code'] = 403

    return validate_company_id_response

def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    
    try:
        # Parse request body
        request_body = json.loads(event.get('body', '{}'))
        
        # Load and validate schema
        schema = load_schema()
        validate(instance=request_body, schema=schema)

        # Get user type from authorizer
        user_type = get_user_type_from_authorizer(event)
        if not user_type:
            return get_response(403, {
                "error": f"Customer cannot create users"
            })

        validate_company_id_response = validate_company_id(request_body['company_id'], user_type)
        if not validate_company_id_response['valid']:
            return get_response(validate_company_id_response['status_code'], {
                "error": validate_company_id_response['error']
            })

        request_body['type'] = user_type

        response = table.query(
            IndexName='email_index',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={
                ':email': request_body['email']
            }
        )

        if response['Items']:
            return get_response(409, {
                "error": "User already exists"
            })
        
        # Hash the password before storing
        request_body['password'] = hash_password(request_body['password'])
        # Add timestamps and generate UUID 
        current_time = datetime.utcnow().isoformat()
        request_body['id'] = str(uuid.uuid4())
        request_body['created_at'] = current_time
        request_body['updated_at'] = current_time
        request_body['status'] = USER_STATUS_ACTIVE if user_type == USER_TYPE_ACCOUNTING else USER_STATUS_PENDING_CONFIRMATION
        
        # Save to DynamoDB with proper error handling
        response = table.put_item(
            Item=request_body,
            ReturnValues='NONE'
        )
        logger.info("Successfully saved to DynamoDB: %s", response)

        # Remove sensitive data from response
        response_body = request_body.copy()
        response_body.pop('password', None)

        # Return success response
        return get_response(201, response_body)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON format")
        return get_response(400, {
            "error": "Invalid JSON format"
        })
    except jsonschema.exceptions.ValidationError as e:
        logger.error("Validation error: %s", str(e))
        return get_response(400, {
            "error": "Validation error",
            "details": str(e)
        })
    except ValueError as e:
        logger.error("Validation error: %s", str(e))
        return get_response(400, {
            "error": "Validation error",
            "details": str(e)
        })
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        return get_response(500, {
            "error": "Internal server error",
            "details": str(e)
        }) 

