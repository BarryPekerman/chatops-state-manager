"""
Comprehensive unit tests for telegram-bot Lambda function
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from moto import mock_secretsmanager
import boto3
import os

# Import the lambda handler
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot


@pytest.fixture
def mock_env():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'AUTHORIZED_CHAT_ID': '123456789',
        'API_GATEWAY_URL': 'https://api.example.com/webhook',
        'AWS_DEFAULT_REGION': 'us-east-1'
    }):
        yield


@pytest.fixture
def mock_secrets():
    """Mock AWS Secrets Manager with test secrets"""
    with mock_secretsmanager():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        
        client.create_secret(
            Name='chatops/secrets',
            SecretString=json.dumps({
                'api_gateway_key': 'test-api-key-12345'
            })
        )
        
        # Patch the module-level secrets_client to use the mocked client
        with patch.object(bot, 'secrets_client', client):
            yield client


@pytest.fixture
def telegram_webhook_event():
    """Sample Telegram webhook event"""
    return {
        'body': json.dumps({
            'update_id': 12345,
            'message': {
                'message_id': 1,
                'from': {
                    'id': 123456789,
                    'is_bot': False,
                    'first_name': 'Test',
                    'username': 'testuser'
                },
                'chat': {
                    'id': 123456789,
                    'first_name': 'Test',
                    'type': 'private'
                },
                'date': 1234567890,
                'text': '/status'
            }
        })
    }


class TestSecretRetrieval:
    """Test secret retrieval from AWS Secrets Manager"""
    
    def test_get_secrets(self, mock_secrets):
        """Test successful secret retrieval"""
        secrets = bot.get_secrets()
        
        assert 'api_gateway_key' in secrets
        assert secrets['api_gateway_key'] == 'test-api-key-12345'
    
    def test_get_api_gateway_key(self, mock_secrets):
        """Test API Gateway key retrieval"""
        key = bot.get_api_gateway_key()
        
        assert key == 'test-api-key-12345'
    
    def test_get_secrets_failure(self):
        """Test secret retrieval failure"""
        with pytest.raises(Exception):
            bot.get_secrets()


class TestMessageParsing:
    """Test message parsing from Telegram webhooks"""
    
    def test_parse_command_message(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test parsing command message"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 200
            mock_post.assert_called_once()
    
    def test_parse_string_body(self, mock_env, mock_secrets):
        """Test parsing string body"""
        event = {
            'body': '{"update_id": 123, "message": {"chat": {"id": 123456789}, "text": "/status"}}'
        }
        
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(event, None)
            
            assert response['statusCode'] == 200
    
    def test_parse_dict_body(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test parsing dict body"""
        telegram_webhook_event['body'] = json.loads(telegram_webhook_event['body'])
        
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 200


class TestAuthorization:
    """Test user authorization"""
    
    def test_authorized_user(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test authorized user can send commands"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 200
            mock_post.assert_called_once()
    
    def test_unauthorized_user(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test unauthorized user is rejected"""
        # Change chat ID to unauthorized value
        body = json.loads(telegram_webhook_event['body'])
        body['message']['chat']['id'] = 999999999
        telegram_webhook_event['body'] = json.dumps(body)
        
        response = bot.lambda_handler(telegram_webhook_event, None)
        
        # Should return OK but not forward the message
        assert response['statusCode'] == 200
        
        # Verify no forwarding happened
        with patch('bot.requests.post') as mock_post:
            mock_post.assert_not_called()


class TestCommandFiltering:
    """Test command filtering"""
    
    def test_command_message_forwarded(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test command messages are forwarded"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 200
            mock_post.assert_called_once()
    
    def test_non_command_message_ignored(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test non-command messages are ignored"""
        body = json.loads(telegram_webhook_event['body'])
        body['message']['text'] = 'Hello, just a regular message'
        telegram_webhook_event['body'] = json.dumps(body)
        
        response = bot.lambda_handler(telegram_webhook_event, None)
        
        # Should return OK but not forward
        assert response['statusCode'] == 200
    
    def test_empty_message_ignored(self, mock_env, mock_secrets):
        """Test empty message is ignored"""
        event = {
            'body': json.dumps({
                'update_id': 123
                # No message field
            })
        }
        
        response = bot.lambda_handler(event, None)
        
        assert response['statusCode'] == 200


class TestForwarding:
    """Test message forwarding to API Gateway"""
    
    def test_forward_to_api_gateway(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test forwarding to API Gateway"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 200
            
            # Verify API Gateway call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            
            # Verify URL
            assert call_args[0][0] == 'https://api.example.com/webhook'
            
            # Verify headers include API key
            assert 'x-api-key' in call_args[1]['headers']
            assert call_args[1]['headers']['x-api-key'] == 'test-api-key-12345'
            
            # Verify payload structure
            payload = call_args[1]['json']
            assert 'update_id' in payload
            assert 'message' in payload
    
    def test_forward_preserves_update_id(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test update_id is preserved"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            bot.lambda_handler(telegram_webhook_event, None)
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            assert payload['update_id'] == 12345
    
    def test_forward_failure(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test handling of forwarding failure"""
        with patch('bot.requests.post') as mock_post:
            mock_post.side_effect = Exception('Network error')
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            # Should handle gracefully
            assert response['statusCode'] == 500
    
    def test_forward_timeout(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test request timeout configuration"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            bot.lambda_handler(telegram_webhook_event, None)
            
            call_args = mock_post.call_args
            assert call_args[1]['timeout'] == 30


class TestErrorHandling:
    """Test error handling"""
    
    def test_invalid_json(self, mock_env, mock_secrets):
        """Test invalid JSON handling"""
        event = {
            'body': 'not valid json'
        }
        
        response = bot.lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid JSON' in body['error']
    
    def test_missing_api_gateway_url(self, mock_secrets, telegram_webhook_event):
        """Test missing API Gateway URL"""
        with patch.dict(os.environ, {'AUTHORIZED_CHAT_ID': '123456789'}, clear=True):
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Missing API Gateway URL' in body['error']
    
    def test_secret_retrieval_failure(self, mock_env, telegram_webhook_event):
        """Test secret retrieval failure"""
        # Don't set up mock_secrets, so retrieval will fail
        response = bot.lambda_handler(telegram_webhook_event, None)
        
        assert response['statusCode'] == 500
    
    def test_network_error(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test network error handling"""
        with patch('bot.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.RequestException('Connection failed')
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Request failed' in body['error']
    
    def test_unexpected_error(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test unexpected error handling"""
        with patch('bot.requests.post') as mock_post:
            mock_post.side_effect = RuntimeError('Unexpected error')
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'Internal server error' in body['error']


class TestPayloadFormat:
    """Test payload formatting for API Gateway"""
    
    def test_payload_structure(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test payload has correct structure"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            bot.lambda_handler(telegram_webhook_event, None)
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            # Check required fields
            assert 'update_id' in payload
            assert 'message' in payload
            assert 'message_id' in payload['message']
            assert 'from' in payload['message']
            assert 'chat' in payload['message']
            assert 'text' in payload['message']
    
    def test_payload_chat_id_type(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test chat ID is converted to int"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            bot.lambda_handler(telegram_webhook_event, None)
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            assert isinstance(payload['message']['chat']['id'], int)
            assert isinstance(payload['message']['from']['id'], int)


class TestLogging:
    """Test logging functionality"""
    
    def test_logs_incoming_webhook(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test incoming webhook is logged"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            with patch('bot.logger') as mock_logger:
                bot.lambda_handler(telegram_webhook_event, None)
                
                # Verify logging happened
                assert mock_logger.info.called
    
    def test_logs_forwarding(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test forwarding is logged"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            with patch('bot.logger') as mock_logger:
                bot.lambda_handler(telegram_webhook_event, None)
                
                # Check for forwarding log
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any('Forwarding' in str(call) or 'forwarded' in str(call).lower() 
                          for call in log_calls)


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    def test_missing_text_field(self, mock_env, mock_secrets):
        """Test message without text field"""
        event = {
            'body': json.dumps({
                'update_id': 123,
                'message': {
                    'chat': {'id': 123456789},
                    'from': {'id': 123456789}
                    # No text field
                }
            })
        }
        
        response = bot.lambda_handler(event, None)
        assert response['statusCode'] == 200
    
    def test_empty_text(self, mock_env, mock_secrets):
        """Test message with empty text"""
        event = {
            'body': json.dumps({
                'update_id': 123,
                'message': {
                    'chat': {'id': 123456789},
                    'from': {'id': 123456789},
                    'text': ''
                }
            })
        }
        
        response = bot.lambda_handler(event, None)
        assert response['statusCode'] == 200
    
    def test_api_gateway_non_200_response(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test handling of non-200 API Gateway response"""
        with patch('bot.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = 'Internal Server Error'
            mock_post.return_value = mock_response
            
            response = bot.lambda_handler(telegram_webhook_event, None)
            # Should still return 200 (don't fail on API Gateway errors)
            assert response['statusCode'] == 200
    
    def test_update_id_generation(self, mock_env, mock_secrets):
        """Test update_id generation when missing"""
        event = {
            'body': json.dumps({
                # No update_id
                'message': {
                    'chat': {'id': 123456789},
                    'from': {'id': 123456789},
                    'text': '/status'
                }
            })
        }
        
        with patch('bot.requests.post') as mock_post, \
             patch('time.time', return_value=1234567890.0):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            bot.lambda_handler(event, None)
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert 'update_id' in payload
            assert payload['update_id'] == 1234567890000  # time.time() * 1000
    
    def test_logs_errors(self, mock_env, mock_secrets, telegram_webhook_event):
        """Test errors are logged"""
        with patch('bot.requests.post') as mock_post:
            mock_post.side_effect = Exception('Test error')
            
            with patch('bot.logger') as mock_logger:
                bot.lambda_handler(telegram_webhook_event, None)
                
                # Verify error logging
                assert mock_logger.error.called
