"""
Comprehensive unit tests for ai-output-processor Lambda function
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
import processor


@pytest.fixture
def mock_env():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'AWS_REGION': 'us-east-1',
        'ENABLE_AI_PROCESSING': 'false',
        'MAX_MESSAGE_LENGTH': '3500',
        'MAX_MESSAGES': '10',
        'AI_THRESHOLD': '1000'
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
                'telegram_bot_token': '123456:ABC-DEF'
            })
        )
        
        yield client


@pytest.fixture
def processing_config():
    """Sample processing configuration"""
    return processor.ProcessingConfig(
        enable_ai_processing=False,
        max_message_length=3500,
        max_messages=10,
        ai_threshold=1000
    )


@pytest.fixture
def sample_terraform_output():
    """Sample Terraform output"""
    return """
Terraform will perform the following actions:

  # aws_lambda_function.example will be destroyed
  - resource "aws_lambda_function" "example" {
      - arn = "arn:aws:lambda:us-east-1:123456789:function:example"
      - function_name = "example"
      - runtime = "python3.11"
    }

Plan: 0 to add, 0 to change, 1 to destroy.
"""


class TestProcessingConfig:
    """Test ProcessingConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = processor.ProcessingConfig()
        
        assert config.enable_ai_processing is False
        assert config.max_message_length == 3500
        assert config.max_messages == 10
        assert config.ai_threshold == 1000
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = processor.ProcessingConfig(
            enable_ai_processing=True,
            max_message_length=5000,
            max_messages=5,
            ai_threshold=2000
        )
        
        assert config.enable_ai_processing is True
        assert config.max_message_length == 5000
        assert config.max_messages == 5
        assert config.ai_threshold == 2000


class TestOutputSanitization:
    """Test output sanitization"""
    
    def test_sanitize_github_tokens(self, mock_secrets, processing_config):
        """Test GitHub token redaction"""
        text = "GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        result = processor_obj.sanitize_output(text)
        
        assert 'ghp_' not in result
        assert '[REDACTED]' in result
    
    def test_sanitize_aws_keys(self, mock_secrets, processing_config):
        """Test AWS key redaction"""
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        result = processor_obj.sanitize_output(text)
        
        assert 'AKIA' not in result or '[REDACTED]' in result
    
    def test_sanitize_passwords(self, mock_secrets, processing_config):
        """Test password redaction"""
        text = "password=super_secret_123"
        
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        result = processor_obj.sanitize_output(text)
        
        assert '[REDACTED]' in result
    
    def test_sanitize_api_keys(self, mock_secrets, processing_config):
        """Test API key redaction"""
        text = "x-api-key: sk-1234567890abcdef"
        
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        result = processor_obj.sanitize_output(text)
        
        assert '[REDACTED]' in result
    
    def test_collapse_multiple_newlines(self, mock_secrets, processing_config):
        """Test collapsing multiple newlines"""
        text = "Line 1\n\n\n\n\nLine 2"
        
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        result = processor_obj.sanitize_output(text)
        
        assert result == "Line 1\n\nLine 2"
    
    def test_sanitize_empty_text(self, mock_secrets, processing_config):
        """Test sanitizing empty text"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        result = processor_obj.sanitize_output("")
        
        assert result == ""


class TestAIProcessingDecision:
    """Test AI processing decision logic"""
    
    def test_should_use_ai_short_output(self, mock_secrets):
        """Test short output doesn't trigger AI"""
        config = processor.ProcessingConfig(
            enable_ai_processing=True,
            ai_threshold=1000
        )
        processor_obj = processor.TerraformOutputProcessor(config)
        
        short_text = "x" * 500
        assert processor_obj.should_use_ai_processing(short_text) is False
    
    def test_should_use_ai_long_output(self, mock_secrets):
        """Test long output triggers AI"""
        config = processor.ProcessingConfig(
            enable_ai_processing=True,
            ai_threshold=1000
        )
        processor_obj = processor.TerraformOutputProcessor(config)
        
        long_text = "x" * 2000
        assert processor_obj.should_use_ai_processing(long_text) is True
    
    def test_ai_disabled(self, mock_secrets):
        """Test AI processing disabled"""
        config = processor.ProcessingConfig(
            enable_ai_processing=False,
            ai_threshold=1000
        )
        processor_obj = processor.TerraformOutputProcessor(config)
        
        long_text = "x" * 2000
        assert processor_obj.should_use_ai_processing(long_text) is False


class TestSimpleProcessing:
    """Test simple processing without AI"""
    
    def test_process_simple_status(self, mock_secrets, processing_config, sample_terraform_output):
        """Test simple processing for status command"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        messages = processor_obj.process_simple(sample_terraform_output, 'status')
        
        assert len(messages) > 0
        assert 'Terraform Status' in messages[0]
        assert '```text' in messages[0]
    
    def test_process_simple_destroy(self, mock_secrets, processing_config, sample_terraform_output):
        """Test simple processing for destroy command"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        messages = processor_obj.process_simple(sample_terraform_output, 'destroy')
        
        assert len(messages) > 0
        assert 'Destroy Plan' in messages[0]
    
    def test_process_simple_truncate_long(self, mock_secrets, processing_config):
        """Test truncation of long output"""
        long_output = "x" * 5000
        
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        messages = processor_obj.process_simple(long_output, 'status')
        
        assert 'truncated' in messages[0]


class TestMessageSplitting:
    """Test message splitting for Telegram"""
    
    def test_split_short_message(self, mock_secrets, processing_config):
        """Test short message doesn't split"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        short_message = "Short message"
        result = processor_obj.split_message(short_message)
        
        assert len(result) == 1
        assert result[0] == short_message
    
    def test_split_long_message(self, mock_secrets, processing_config):
        """Test long message splits correctly"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        # Create a message longer than max_message_length
        long_message = "Line\n" * 1000
        result = processor_obj.split_message(long_message)
        
        assert len(result) > 1
        for msg in result:
            assert len(msg) <= processing_config.max_message_length + 100  # Allow some overhead
    
    def test_split_respects_max_messages(self, mock_secrets, processing_config):
        """Test message count limit"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        # Create a very long message that would split into many messages
        very_long_message = "Line\n" * 10000
        result = processor_obj.split_message(very_long_message)
        
        assert len(result) <= processing_config.max_messages


class TestTelegramMessaging:
    """Test Telegram message sending"""
    
    def test_send_telegram_message_success(self, mock_secrets, processing_config):
        """Test successful message send"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch('processor.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'ok': True, 'result': {}}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            result = processor_obj.send_telegram_message('123456789', 'Test message')
            
            assert result['ok'] is True
            mock_post.assert_called_once()
    
    def test_send_telegram_message_failure(self, mock_secrets, processing_config):
        """Test message send failure"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch('processor.requests.post') as mock_post:
            mock_post.side_effect = Exception('Network error')
            
            with pytest.raises(Exception):
                processor_obj.send_telegram_message('123456789', 'Test message')
    
    def test_send_multiple_messages(self, mock_secrets, processing_config):
        """Test sending multiple messages"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch('processor.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'ok': True}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            messages = ['Message 1', 'Message 2', 'Message 3']
            results = processor_obj.send_telegram_messages('123456789', messages)
            
            assert len(results) == 3
            assert mock_post.call_count == 3


class TestProcessOutput:
    """Test main process_output method"""
    
    def test_process_output_simple(self, mock_env, mock_secrets, sample_terraform_output):
        """Test processing with simple mode"""
        config = processor.ProcessingConfig(enable_ai_processing=False)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        with patch.object(processor_obj, 'send_telegram_messages') as mock_send:
            mock_send.return_value = [{'ok': True}]
            
            result = processor_obj.process_output(
                sample_terraform_output,
                'status',
                '123456789'
            )
            
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['success'] is True
            assert body['processing_method'] == 'simple'
    
    def test_process_output_error_handling(self, mock_secrets, processing_config):
        """Test error handling in process_output"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch.object(processor_obj, 'send_telegram_messages') as mock_send:
            mock_send.side_effect = Exception('Send failed')
            
            result = processor_obj.process_output(
                'test output',
                'status',
                '123456789'
            )
            
            assert result['statusCode'] == 500


class TestLambdaHandler:
    """Test Lambda handler function"""
    
    def test_lambda_handler_success(self, mock_env, mock_secrets):
        """Test successful lambda invocation"""
        event = {
            'body': json.dumps({
                'raw_output': 'Terraform output',
                'command': 'status',
                'chat_id': '123456789'
            })
        }
        
        with patch('processor.TerraformOutputProcessor.process_output') as mock_process:
            mock_process.return_value = {
                'statusCode': 200,
                'body': json.dumps({'success': True})
            }
            
            result = processor.lambda_handler(event, None)
            
            assert result['statusCode'] == 200
    
    def test_lambda_handler_missing_params(self, mock_env, mock_secrets):
        """Test lambda with missing parameters"""
        event = {
            'body': json.dumps({
                'command': 'status'
                # Missing raw_output and chat_id
            })
        }
        
        result = processor.lambda_handler(event, None)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert 'Missing required parameters' in body['error']
    
    def test_lambda_handler_string_body(self, mock_env, mock_secrets):
        """Test lambda with string body"""
        event = {
            'body': '{"raw_output": "test", "command": "status", "chat_id": "123"}'
        }
        
        with patch('processor.TerraformOutputProcessor.process_output') as mock_process:
            mock_process.return_value = {
                'statusCode': 200,
                'body': json.dumps({'success': True})
            }
            
            result = processor.lambda_handler(event, None)
            
            assert result['statusCode'] == 200
    
    def test_lambda_handler_error(self, mock_env, mock_secrets):
        """Test lambda handler error handling"""
        event = {
            'body': 'invalid json'
        }
        
        result = processor.lambda_handler(event, None)
        
        assert result['statusCode'] == 500


class TestAIProcessing:
    """Test AI processing with Bedrock"""
    
    def test_create_bedrock_prompt(self, mock_secrets, processing_config):
        """Test Bedrock prompt creation"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        prompt = processor_obj.create_bedrock_prompt('test output', 'status')
        
        assert 'DevOps assistant' in prompt
        assert 'status' in prompt.lower()
        assert 'test output' in prompt
    
    def test_format_ai_summary(self, mock_secrets, processing_config):
        """Test AI summary formatting"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        summary = "Resources: 5 total, 2 added, 1 changed, 0 destroyed"
        result = processor_obj.format_ai_summary(summary, 'status')
        
        assert len(result) > 0
        assert 'Status Summary' in result[0]
        assert summary in result[0]
    
    def test_process_with_ai_fallback(self, mock_secrets):
        """Test AI processing fallback to simple on error"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        with patch('processor.bedrock_client.invoke_model') as mock_bedrock:
            mock_bedrock.side_effect = Exception('Bedrock error')
            
            result = processor_obj.process_with_ai('test output', 'status')
            
            # Should fallback to simple processing
            assert len(result) > 0
            assert 'Terraform Status' in result[0]


class TestSecretRetrieval:
    """Test secret retrieval"""
    
    def test_get_secrets(self, mock_secrets):
        """Test secret retrieval"""
        secrets = processor.get_secrets()
        
        assert 'telegram_bot_token' in secrets
        assert secrets['telegram_bot_token'] == '123456:ABC-DEF'
    
    def test_get_telegram_bot_token(self, mock_secrets):
        """Test Telegram bot token retrieval"""
        token = processor.get_telegram_bot_token()
        
        assert token == '123456:ABC-DEF'
