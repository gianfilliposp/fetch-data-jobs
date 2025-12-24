import json
import jsonschema
import os
import boto3
import logging
import jwt
from datetime import datetime, timedelta
from jsonschema import validate
from Utils import get_response
from Constants import USER_STATUS_INACTIVE, USER_TYPE_CUSTOMER
from Utils import verify_password

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(f"users-table-{os.environ.get('ENVIRONMENT')}")
companies_table = dynamodb.Table(f"companies-table-{os.environ.get('ENVIRONMENT')}")

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key')  # Make sure to set this in your environment
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION = 24  # hours

def generate_token(user_data):
    expiration = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION)
    token_data = {
        'id': user_data['id'],
        'email': user_data['email'],
        'type': user_data['type'],
        'company_id': user_data['company_id'],
        'exp': expiration
    }
    return jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

def load_schema():
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.json')
    with open(schema_path, 'r') as f:
        return json.load(f)


def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    
    try:
        # Parse request body
        request_body = json.loads(event.get('body', '{}'))
        
        # Load and validate schema
        schema = load_schema()
        validate(instance=request_body, schema=schema)
        
        # Get user from DynamoDB by email
        response = table.query(
            IndexName='email_index',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={
                ':email': request_body['email']
            }
        )
        
        if not response['Items']:
            return get_response(401, {
                "error": "Invalid credentials"
            })
            
        user = response['Items'][0]
        
        # Check if user is active
        if user.get('status') == USER_STATUS_INACTIVE:
            return get_response(401, {
                "error": "Account is inactive"
            })
        
        # Verify password
        if not verify_password(user['password'], request_body['password']):
            return get_response(401, {
                "error": "Invalid credentials"
            })
            
        # Remove sensitive data from response
        user.pop('password', None)
        
        # Generate JWT token
        token = generate_token(user)
        
        # If user is a customer, fetch their company data
        response_data = {
            'user': user,
            'token': token
        }
        
        if user.get('type') == USER_TYPE_CUSTOMER:
            company_response = companies_table.get_item(
                Key={'id': user.get('company_id')}
            )
            if 'Item' in company_response:
                response_data['company'] = company_response['Item']
        
        # Return success response with user data and token
        return get_response(200, response_data)
        
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
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        return get_response(500, {
            "error": "Internal server error",
            "details": str(e)
        }) 