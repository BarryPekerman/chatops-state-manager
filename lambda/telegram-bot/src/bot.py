import json
import os
import requests
import time
import logging
import boto3
from typing import Dict, Any

# Common response helper
def create_response(status_code: int, body: Any) -> Dict[str, Any]:
    """Helper to create standardized HTTP responses"""
    return {
        'statusCode': status_code,
        'body': json.dumps(body) if isinstance(body, dict) else body
    }

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS Secrets Manager client
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'eu-west-1'))

def get_secrets():
    """
    Retrieve all secrets from AWS Secrets Manager (JSON bundle)
    """
    try:
        response = secrets_client.get_secret_value(SecretId='chatops/secrets')
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Failed to retrieve secrets from Secrets Manager: {e}")
        raise

def get_api_gateway_key():
    """
    Retrieve API Gateway key from AWS Secrets Manager
    """
    secrets = get_secrets()
    return secrets['api_gateway_key']

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Telegram bot webhook.

    This function receives Telegram webhooks and forwards commands
    to the main API Gateway webhook handler. It acts as a proxy
    between Telegram and the main webhook handler.
    """
    try:
        # Parse the request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        logger.info(f"Received Telegram webhook: {json.dumps(body, indent=2)}")

        # Extract message information
        if 'message' not in body:
            logger.warning("No message in webhook body")
            return create_response(200, {'ok': True})

        message = body['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        # Check if user is authorized
        authorized_chat_id = os.environ.get('AUTHORIZED_CHAT_ID')
        if str(chat_id) != str(authorized_chat_id):
            logger.warning(f"Unauthorized chat ID: {chat_id}")
            return create_response(200, {'ok': True})

        # Check if it's a command
        if not text.startswith('/'):
            logger.info(f"Non-command message from {chat_id}: {text}")
            return create_response(200, {'ok': True})

        logger.info(f"Processing command from {chat_id}: {text}")

        # Forward to main API Gateway
        api_gateway_url = os.environ.get('API_GATEWAY_URL')
        
        if not api_gateway_url:
            logger.error("Missing API Gateway URL configuration")
            return create_response(500, {'error': 'Missing API Gateway URL configuration'})

        # Get API Gateway key from Secrets Manager
        try:
            api_gateway_key = get_api_gateway_key()
        except Exception as e:
            logger.error(f"Failed to retrieve API Gateway key: {e}")
            return create_response(500, {'error': 'Failed to retrieve API Gateway key'})

        # Prepare payload in Telegram webhook format for main webhook
        # Use the real Telegram update_id from the webhook payload
        update_id = body.get('update_id', int(time.time() * 1000))

        payload = {
            'update_id': update_id,
            'message': {
                'message_id': 1,
                'from': {
                    'id': int(chat_id),
                    'is_bot': False,
                    'first_name': 'Telegram User'
                },
                'chat': {
                    'id': int(chat_id),
                    'first_name': 'Telegram User',
                    'type': 'private'
                },
                'date': int(time.time()),
                'text': text
            }
        }

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_gateway_key
        }

        logger.info(f"Forwarding to {api_gateway_url} with API key: {api_gateway_key[:5]}...")

        # Send to main webhook handler
        response = requests.post(
            api_gateway_url,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            logger.info(f"Successfully forwarded command to main webhook")
        else:
            logger.error(f"Failed to forward command: {response.status_code} - {response.text}")

        return create_response(200, {'ok': True})

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return create_response(400, {'error': 'Invalid JSON'})
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return create_response(500, {'error': 'Request failed'})
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return create_response(500, {'error': 'Internal server error'})
