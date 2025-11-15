"""
Integration tests for complete message flow
Tests: Telegram → Webhook Handler → GitHub → AI Processor → Telegram
"""
import json
import os
import time
import pytest
import requests
import boto3
from moto import mock_secretsmanager


# Configuration from environment
LOCALSTACK_URL = os.environ.get('AWS_ENDPOINT_URL', 'http://localstack:4566')
MOCK_GITHUB_URL = os.environ.get('MOCK_GITHUB_URL', 'http://mock-github:5000')
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')


class TestSecretsSetup:
    """Test that secrets are properly set up in LocalStack"""
    
    @pytest.fixture(autouse=True)
    def setup_secrets(self):
        """Set up secrets in LocalStack before each test"""
        client = boto3.client(
            'secretsmanager',
            region_name=AWS_REGION,
            endpoint_url=LOCALSTACK_URL,
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        # Create secrets bundle
        try:
            client.create_secret(
                Name='chatops/secrets',
                SecretString=json.dumps({
                    'github_token': 'ghp_test_token_12345',
                    'telegram_bot_token': '123456:ABC-DEF',
                    'api_gateway_key': 'test-api-key',
                    'telegram_secret_token': 'test-secret-token'
                })
            )
        except client.exceptions.ResourceExistsException:
            # Secret already exists, update it
            client.put_secret_value(
                SecretId='chatops/secrets',
                SecretString=json.dumps({
                    'github_token': 'ghp_test_token_12345',
                    'telegram_bot_token': '123456:ABC-DEF',
                    'api_gateway_key': 'test-api-key',
                    'telegram_secret_token': 'test-secret-token'
                })
            )
        
        yield
        
        # Cleanup after test
        try:
            client.delete_secret(
                SecretId='chatops/secrets',
                ForceDeleteWithoutRecovery=True
            )
        except:
            pass
    
    def test_secrets_accessible(self):
        """Test that secrets can be retrieved"""
        client = boto3.client(
            'secretsmanager',
            region_name=AWS_REGION,
            endpoint_url=LOCALSTACK_URL,
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        response = client.get_secret_value(SecretId='chatops/secrets')
        secrets = json.loads(response['SecretString'])
        
        assert 'github_token' in secrets
        assert 'telegram_bot_token' in secrets
        assert secrets['github_token'] == 'ghp_test_token_12345'


class TestMockGitHub:
    """Test mock GitHub server functionality"""
    
    @pytest.fixture(autouse=True)
    def clear_dispatches(self):
        """Clear dispatches before each test"""
        try:
            requests.delete(f"{MOCK_GITHUB_URL}/test/dispatches", timeout=5)
        except:
            pass
        yield
    
    def test_mock_github_healthy(self):
        """Test that mock GitHub server is accessible"""
        response = requests.get(f"{MOCK_GITHUB_URL}/health", timeout=5)
        assert response.status_code == 200
        assert response.json()['status'] == 'healthy'
    
    def test_repository_dispatch(self):
        """Test repository dispatch endpoint"""
        payload = {
            'event_type': 'telegram_command',
            'client_payload': {
                'command': 'status'
            }
        }
        
        response = requests.post(
            f"{MOCK_GITHUB_URL}/repos/test-owner/test-repo/dispatches",
            json=payload,
            headers={'Authorization': 'token test-token'},
            timeout=5
        )
        
        assert response.status_code == 204
        
        # Verify dispatch was received
        time.sleep(0.5)
        dispatches = requests.get(f"{MOCK_GITHUB_URL}/test/dispatches", timeout=5)
        data = dispatches.json()
        
        assert data['count'] >= 1
        assert data['dispatches'][-1]['event_type'] == 'telegram_command'
        assert data['dispatches'][-1]['client_payload']['command'] == 'status'


class TestWebhookHandlerIntegration:
    """Test webhook handler in isolation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for webhook handler tests"""
        # Setup secrets
        client = boto3.client(
            'secretsmanager',
            region_name=AWS_REGION,
            endpoint_url=LOCALSTACK_URL,
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        try:
            client.create_secret(
                Name='chatops/secrets',
                SecretString=json.dumps({
                    'github_token': 'ghp_test_token_12345',
                    'telegram_bot_token': '123456:ABC-DEF',
                    'api_gateway_key': 'test-api-key'
                })
            )
        except:
            pass
        
        # Clear mock GitHub dispatches
        try:
            requests.delete(f"{MOCK_GITHUB_URL}/test/dispatches", timeout=5)
        except:
            pass
        
        yield
    
    def test_webhook_handler_status_command(self):
        """Test webhook handler processes status command"""
        # Import webhook handler
        import sys
        sys.path.insert(0, '/lambda/webhook-handler/src')
        import webhook_handler
        
        # Set environment
        os.environ['AUTHORIZED_CHAT_ID'] = '123456789'
        os.environ['GITHUB_OWNER'] = 'test-owner'
        os.environ['GITHUB_REPO'] = 'test-repo'
        os.environ['AWS_ENDPOINT_URL'] = LOCALSTACK_URL
        
        # Mock GitHub API to point to our mock server
        # Store original post function to avoid any recursion issues
        original_post = requests.post
        
        with pytest.MonkeyPatch.context() as m:
            def mock_post(url, **kwargs):
                # Redirect to mock GitHub - use defensive string operations
                # Convert url to string first to avoid any weird object issues
                try:
                    # Safely convert url to string
                    if type(url) is str:
                        url_str = url
                    else:
                        url_str = str(url) if url is not None else ''
                    
                    # Check if it's a GitHub URL using simple string check
                    if 'github.com' in url_str:
                        # Replace using simple string operations
                        mock_url = url_str.replace('https://api.github.com', MOCK_GITHUB_URL)
                        # Use original requests.post to avoid any circular issues
                        return original_post(mock_url, **kwargs)
                    # Not a GitHub URL, use original
                    return original_post(url_str, **kwargs)
                except (RecursionError, Exception):
                    # If anything causes recursion, fall back to original
                    return original_post(url, **kwargs)
            
            m.setattr(webhook_handler.requests, 'post', mock_post)
            
            # Create test event
            event = {
                'body': json.dumps({
                    'message': {
                        'chat': {'id': 123456789},
                        'from': {'id': 123456789, 'username': 'testuser'},
                        'text': '/status'
                    }
                })
            }
            
            # Call handler
            response = webhook_handler.lambda_handler(event, None)
            
            assert response['statusCode'] == 200
            
            # Verify GitHub dispatch was triggered
            time.sleep(1)
            dispatches = requests.get(f"{MOCK_GITHUB_URL}/test/dispatches", timeout=5)
            data = dispatches.json()
            
            assert data['count'] >= 1


class TestOutputSanitization:
    """Test output sanitization across the system"""
    
    def test_sanitize_secrets_in_output(self):
        """Test that secrets are properly sanitized"""
        import sys
        sys.path.insert(0, '/lambda/webhook-handler/src')
        import webhook_handler
        
        # Test various secret patterns
        test_cases = [
            ("Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz", "[REDACTED]"),
            ("AWS_KEY=AKIAIOSFODNN7EXAMPLE", "[REDACTED]"),
            ("password=secret123", "[REDACTED]"),
        ]
        
        for input_text, expected_pattern in test_cases:
            result = webhook_handler.sanitize_workflow_output(input_text)
            assert expected_pattern in result
            # Ensure original secret is not in output
            if "ghp_" in input_text:
                assert "ghp_" not in result
            if "AKIA" in input_text:
                assert "AKIA" not in result


class TestEndToEndFlow:
    """Test complete end-to-end message flow"""
    
    @pytest.mark.timeout(30)
    def test_complete_flow_simulation(self):
        """
        Simulate complete flow:
        1. Telegram message arrives
        2. Webhook handler processes it
        3. GitHub workflow is triggered
        4. Workflow completes and sends callback
        5. AI processor processes output
        6. Response sent back to Telegram
        
        Note: This is a simplified simulation due to container limitations
        """
        # Setup secrets
        client = boto3.client(
            'secretsmanager',
            region_name=AWS_REGION,
            endpoint_url=LOCALSTACK_URL,
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        try:
            client.create_secret(
                Name='chatops/secrets',
                SecretString=json.dumps({
                    'github_token': 'ghp_test_token_12345',
                    'telegram_bot_token': '123456:ABC-DEF',
                    'api_gateway_key': 'test-api-key'
                })
            )
        except:
            pass
        
        # Step 1: Clear mock GitHub dispatches
        requests.delete(f"{MOCK_GITHUB_URL}/test/dispatches", timeout=5)
        
        # Step 2: Import and call webhook handler
        import sys
        sys.path.insert(0, '/lambda/webhook-handler/src')
        import webhook_handler
        
        os.environ['AUTHORIZED_CHAT_ID'] = '123456789'
        os.environ['GITHUB_OWNER'] = 'test-owner'
        os.environ['GITHUB_REPO'] = 'test-repo'
        os.environ['AWS_ENDPOINT_URL'] = LOCALSTACK_URL
        
        telegram_event = {
            'body': json.dumps({
                'message': {
                    'chat': {'id': 123456789},
                    'from': {'id': 123456789, 'username': 'testuser'},
                    'text': '/status'
                }
            })
        }
        
        # Mock requests to use mock GitHub
        original_post = requests.post
        
        def mock_post(url, **kwargs):
            if 'github.com' in url:
                mock_url = url.replace('https://api.github.com', MOCK_GITHUB_URL)
                return original_post(mock_url, **kwargs)
            return original_post(url, **kwargs)
        
        import webhook_handler as wh
        wh.requests.post = mock_post
        
        # Call webhook handler
        response = webhook_handler.lambda_handler(telegram_event, None)
        
        # Step 3: Verify GitHub dispatch was triggered
        time.sleep(1)
        dispatches = requests.get(f"{MOCK_GITHUB_URL}/test/dispatches", timeout=5)
        data = dispatches.json()
        
        assert data['count'] >= 1
        last_dispatch = data['dispatches'][-1]
        assert last_dispatch['event_type'] == 'telegram_command'
        assert last_dispatch['client_payload']['command'] == 'status'
        
        print(f"✓ Integration test passed: Complete flow simulation successful")
        print(f"  - Webhook handler: {response['statusCode']}")
        print(f"  - GitHub dispatches: {data['count']}")


class TestErrorHandling:
    """Test error handling in integration scenarios"""
    
    def test_unauthorized_user(self):
        """Test that unauthorized users are rejected"""
        import sys
        sys.path.insert(0, '/lambda/webhook-handler/src')
        import webhook_handler
        
        os.environ['AUTHORIZED_CHAT_ID'] = '123456789'
        os.environ['AWS_ENDPOINT_URL'] = LOCALSTACK_URL
        
        # Setup secrets
        client = boto3.client(
            'secretsmanager',
            region_name=AWS_REGION,
            endpoint_url=LOCALSTACK_URL,
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        try:
            client.create_secret(
                Name='chatops/secrets',
                SecretString=json.dumps({'github_token': 'test', 'telegram_bot_token': 'test'})
            )
        except:
            pass
        
        event = {
            'body': json.dumps({
                'message': {
                    'chat': {'id': 999999999},  # Unauthorized
                    'from': {'id': 999999999, 'username': 'hacker'},
                    'text': '/status'
                }
            })
        }
        
        response = webhook_handler.lambda_handler(event, None)
        
        assert response['statusCode'] == 403
        assert 'Unauthorized' in json.loads(response['body'])['error']
    
    def test_missing_secrets(self):
        """Test handling of missing secrets"""
        import sys
        sys.path.insert(0, '/lambda/webhook-handler/src')
        import webhook_handler
        
        # Ensure secrets are deleted before testing
        client = boto3.client(
            'secretsmanager',
            region_name=AWS_REGION,
            endpoint_url=LOCALSTACK_URL,
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        # Delete secret if it exists
        try:
            client.delete_secret(
                SecretId='chatops/secrets',
                ForceDeleteWithoutRecovery=True
            )
            # Wait a bit for deletion to complete
            time.sleep(0.5)
        except:
            pass  # Secret might not exist, which is fine
        
        os.environ['AWS_ENDPOINT_URL'] = LOCALSTACK_URL
        
        # Now get_secrets should raise an exception
        with pytest.raises(Exception):
            webhook_handler.get_secrets()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])





