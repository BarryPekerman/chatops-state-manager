"""
Comprehensive unit tests for webhook-handler Lambda function
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from moto import mock_secretsmanager
import boto3
import os

# Import the lambda handler (will be in parent directory when run)
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import webhook_handler


@pytest.fixture
def mock_env():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'AUTHORIZED_CHAT_ID': '123456789',
        'GITHUB_OWNER': 'test-owner',
        'GITHUB_REPO': 'test-repo',
        'AWS_DEFAULT_REGION': 'us-east-1'
    }):
        yield


@pytest.fixture
def mock_secrets():
    """Mock AWS Secrets Manager with test secrets"""
    with mock_secretsmanager():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        
        # Create the secrets bundle
        client.create_secret(
            Name='chatops/secrets',
            SecretString=json.dumps({
                'github_token': 'ghp_test_token_12345',
                'telegram_bot_token': '123456:ABC-DEF',
                'api_gateway_key': 'test-api-key',
                'telegram_secret_token': 'test-secret-token'
            })
        )
        
        # Patch the module-level secrets_client to use the mocked client
        with patch.object(webhook_handler, 'secrets_client', client):
            yield client


@pytest.fixture
def telegram_message_event():
    """Sample Telegram message event"""
    return {
        'httpMethod': 'POST',
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'update_id': 12345,
            'message': {
                'message_id': 1,
                'from': {
                    'id': 123456789,
                    'username': 'testuser'
                },
                'chat': {
                    'id': 123456789,
                    'type': 'private'
                },
                'date': 1234567890,
                'text': '/status'
            }
        })
    }


class TestSecretRetrieval:
    """Test secret retrieval from AWS Secrets Manager"""
    
    def test_get_secrets_success(self, mock_secrets):
        """Test successful secret retrieval"""
        secrets = webhook_handler.get_secrets()
        
        assert 'github_token' in secrets
        assert 'telegram_bot_token' in secrets
        assert secrets['github_token'] == 'ghp_test_token_12345'
    
    def test_get_github_token(self, mock_secrets):
        """Test GitHub token retrieval"""
        token = webhook_handler.get_github_token()
        assert token == 'ghp_test_token_12345'
    
    def test_get_telegram_bot_token(self, mock_secrets):
        """Test Telegram bot token retrieval"""
        token = webhook_handler.get_telegram_bot_token()
        assert token == '123456:ABC-DEF'
    
    def test_get_secrets_failure(self):
        """Test secret retrieval failure handling"""
        with pytest.raises(Exception):
            webhook_handler.get_secrets()


class TestCommandParsing:
    """Test command parsing and authorization"""
    
    def test_status_command(self, mock_env, mock_secrets, telegram_message_event):
        """Test /status command processing"""
        with patch('webhook_handler.trigger_github_workflow') as mock_trigger:
            mock_trigger.return_value = {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'})
            }
            
            response = webhook_handler.lambda_handler(telegram_message_event, None)
            
            assert response['statusCode'] == 200
            mock_trigger.assert_called_once_with('status', 123456789)
    
    def test_destroy_command(self, mock_env, mock_secrets, telegram_message_event):
        """Test /destroy command processing"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 123456789, 'username': 'testuser'},
                'chat': {'id': 123456789},
                'text': '/destroy'
            }
        })
        
        with patch('webhook_handler.trigger_github_workflow') as mock_trigger:
            mock_trigger.return_value = {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'})
            }
            
            response = webhook_handler.lambda_handler(telegram_message_event, None)
            
            assert response['statusCode'] == 200
            mock_trigger.assert_called_once_with('destroy', 123456789)
    
    def test_confirm_destroy_command_with_token(self, mock_env, mock_secrets, telegram_message_event):
        """Test /confirm_destroy command with token"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 123456789, 'username': 'testuser'},
                'chat': {'id': 123456789},
                'text': '/confirm_destroy token123'
            }
        })
        
        with patch('webhook_handler.trigger_github_workflow') as mock_trigger:
            mock_trigger.return_value = {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'})
            }
            
            response = webhook_handler.lambda_handler(telegram_message_event, None)
            
            assert response['statusCode'] == 200
            mock_trigger.assert_called_once_with('confirm_destroy', 123456789, 'token123')
    
    def test_unauthorized_chat_id(self, mock_env, mock_secrets, telegram_message_event):
        """Test unauthorized chat ID rejection"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 999999999, 'username': 'hacker'},
                'chat': {'id': 999999999},
                'text': '/status'
            }
        })
        
        response = webhook_handler.lambda_handler(telegram_message_event, None)
        
        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert 'Unauthorized' in body['error']
    
    def test_non_command_message(self, mock_env, mock_secrets, telegram_message_event):
        """Test non-command message handling"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 123456789, 'username': 'testuser'},
                'chat': {'id': 123456789},
                'text': 'hello world'
            }
        })
        
        response = webhook_handler.lambda_handler(telegram_message_event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Not a command'
    
    def test_unknown_command(self, mock_env, mock_secrets, telegram_message_event):
        """Test unknown command handling"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 123456789, 'username': 'testuser'},
                'chat': {'id': 123456789},
                'text': '/unknown'
            }
        })
        
        response = webhook_handler.lambda_handler(telegram_message_event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'Unknown command' in body['message']


class TestCORSHandling:
    """Test CORS preflight request handling"""
    
    def test_cors_preflight(self, mock_env, mock_secrets):
        """Test CORS preflight OPTIONS request"""
        event = {
            'httpMethod': 'OPTIONS',
            'headers': {}
        }
        
        response = webhook_handler.lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'


class TestGitHubWorkflowTrigger:
    """Test GitHub Actions workflow triggering"""
    
    def test_trigger_github_workflow_success(self, mock_env, mock_secrets):
        """Test successful GitHub workflow trigger"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 204
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            with patch('webhook_handler.send_telegram_feedback'):
                response = webhook_handler.trigger_github_workflow('status', 123456789)
                
                assert response['statusCode'] == 200
                mock_post.assert_called_once()
                
                # Verify GitHub API call
                call_args = mock_post.call_args
                assert 'github.com' in call_args[0][0]
                assert call_args[1]['headers']['Authorization'] == 'token ghp_test_token_12345'
    
    def test_trigger_github_workflow_with_token(self, mock_env, mock_secrets):
        """Test GitHub workflow trigger with token"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 204
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            with patch('webhook_handler.send_telegram_feedback'):
                response = webhook_handler.trigger_github_workflow('confirm_destroy', 123456789, 'token123')
                
                assert response['statusCode'] == 200
                
                # Verify token in payload
                call_args = mock_post.call_args
                payload = call_args[1]['json']
                assert payload['client_payload']['token'] == 'token123'
    
    def test_trigger_github_workflow_failure(self, mock_env, mock_secrets):
        """Test GitHub workflow trigger failure"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_post.side_effect = Exception('Network error')
            
            response = webhook_handler.trigger_github_workflow('status', 123456789)
            
            assert response['statusCode'] == 500
    
    def test_missing_github_config(self, mock_secrets):
        """Test missing GitHub configuration"""
        with patch.dict(os.environ, {}, clear=True):
            response = webhook_handler.trigger_github_workflow('status', 123456789)
            
            assert response['statusCode'] == 500


class TestTelegramFeedback:
    """Test Telegram feedback messages"""
    
    def test_send_telegram_feedback_status(self, mock_secrets):
        """Test status command feedback"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            webhook_handler.send_telegram_feedback(123456789, 'status')
            
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert 'Status Check' in payload['text']
    
    def test_send_telegram_feedback_destroy(self, mock_secrets):
        """Test destroy command feedback with token"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            webhook_handler.send_telegram_feedback(123456789, 'destroy', 'token123')
            
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert 'Destroy Plan' in payload['text']
            assert 'token123' in payload['text']


class TestCallbackMode:
    """Test callback mode from GitHub Actions"""
    
    def test_callback_processing(self, mock_env, mock_secrets):
        """Test callback from GitHub Actions"""
        callback_event = {
            'body': json.dumps({
                'callback': True,
                'chat_id': 123456789,
                'command': 'status',
                'run_id': 'run123',
                'raw_output': 'Terraform output here'
            })
        }
        
        with patch('webhook_handler.send_telegram_message_env') as mock_send:
            response = webhook_handler.lambda_handler(callback_event, None)
            
            assert response['statusCode'] == 200
            mock_send.assert_called_once()


class TestOutputSanitization:
    """Test output sanitization for security"""
    
    def test_sanitize_github_tokens(self):
        """Test GitHub token redaction"""
        text = "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        result = webhook_handler.sanitize_workflow_output(text)
        assert 'ghp_' not in result
        assert '[REDACTED]' in result
    
    def test_sanitize_aws_keys(self):
        """Test AWS key redaction"""
        text = "AWS_ACCESS_KEY_ID: AKIAIOSFODNN7EXAMPLE"
        result = webhook_handler.sanitize_workflow_output(text)
        assert 'AKIA' not in result
        assert '[REDACTED]' in result
    
    def test_sanitize_long_output(self):
        """Test output truncation"""
        text = "x" * 15000
        result = webhook_handler.sanitize_workflow_output(text)
        assert len(result) <= 12100
        assert 'truncated' in result


class TestErrorHandling:
    """Test error handling"""
    
    def test_malformed_json(self, mock_env, mock_secrets):
        """Test malformed JSON handling"""
        event = {
            'body': 'not valid json'
        }
        
        response = webhook_handler.lambda_handler(event, None)
        assert response['statusCode'] == 500
    
    def test_missing_body(self, mock_env, mock_secrets):
        """Test missing body handling"""
        event = {
            'httpMethod': 'POST'
        }
        
        response = webhook_handler.lambda_handler(event, None)
        # Should handle gracefully
        assert response['statusCode'] in [200, 403, 500]
