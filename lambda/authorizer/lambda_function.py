import json
import jwt
import os
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key')
JWT_ALGORITHM = 'HS256'

def generate_policy(context, is_authorized):
    policy = {
        "principalId": "authorizer-lamba-function",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow" if is_authorized else "Deny",
                    "Resource": "*"
                }
            ]
        }
    }
    if context and isinstance(context, dict):
        policy['context'] = context
    return policy

def lambda_handler(event, context):
    logger.info("Received event: %s", event)
    
    try:
        # Get the authorization token from the event
        auth_token = event.get('headers', {}).get('authorization')

        if not auth_token:
            logger.error("No authorization token provided")
            return generate_policy(None, False)
            
        # Remove 'Bearer ' prefix if present
        if auth_token.startswith('Bearer '):
            auth_token = auth_token[7:]
            
        # Verify and decode the token
        try:
            decoded = jwt.decode(auth_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            logger.info("Token successfully decoded: %s", decoded)
            
            return generate_policy(decoded, True)
            
        except jwt.ExpiredSignatureError:
            logger.error("Token has expired")
            return generate_policy(None, False)
        except jwt.InvalidTokenError as e:
            logger.error("Invalid token: %s", str(e))
            return generate_policy(None, False)
            
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        return generate_policy(None, False) 