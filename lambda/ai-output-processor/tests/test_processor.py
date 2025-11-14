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
        max_messages=10
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
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = processor.ProcessingConfig(
            enable_ai_processing=True,
            max_message_length=5000,
            max_messages=5
        )
        
        assert config.enable_ai_processing is True
        assert config.max_message_length == 5000
        assert config.max_messages == 5


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
            assert 'processing_method' in body
    
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
    
    def test_summarize_error_with_ai(self, mock_secrets, processing_config):
        """Test error summarization with AI"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        error_text = "Error: Resource not found\nDetails: The resource does not exist"
        
        with patch.object(processor_obj, '_invoke_bedrock') as mock_invoke:
            mock_invoke.return_value = "The resource was not found. Please check if it exists."
            
            result = processor_obj.summarize_error_with_ai(error_text)
            
            assert len(result) > 0
            mock_invoke.assert_called_once()
    
    def test_analyze_risk_with_ai(self, mock_secrets, processing_config):
        """Test risk analysis with AI"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        plan_text = "Plan: 0 to add, 0 to change, 5 to destroy"
        plan_summary = {'to_add': 0, 'to_change': 0, 'to_destroy': 5}
        
        with patch.object(processor_obj, '_invoke_bedrock') as mock_invoke:
            mock_invoke.return_value = "High risk: Destroying 5 resources including databases"
            
            result = processor_obj.analyze_risk_with_ai(plan_text, plan_summary)
            
            assert len(result) > 0
            mock_invoke.assert_called_once()
    
    def test_bedrock_invocation_failure(self, mock_secrets, processing_config):
        """Test Bedrock invocation failure handling"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        with patch('processor.bedrock_client.invoke_model') as mock_bedrock:
            mock_bedrock.side_effect = Exception('Bedrock error')
            
            result = processor_obj._invoke_bedrock('test prompt')
            
            assert result == ""
    
    def test_bedrock_empty_response(self, mock_secrets, processing_config):
        """Test Bedrock empty response handling"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        with patch('processor.bedrock_client.invoke_model') as mock_bedrock:
            mock_response = Mock()
            mock_response.get.return_value = {}
            mock_response.__getitem__ = lambda self, key: {'body': Mock(read=lambda: json.dumps({'results': []}))}[key]
            mock_bedrock.return_value = mock_response
            
            result = processor_obj._invoke_bedrock('test prompt')
            
            assert result == ""


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


class TestPlanExtraction:
    """Test plan summary extraction"""
    
    def test_extract_plan_summary(self, mock_secrets, processing_config):
        """Test plan summary extraction"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "Plan: 2 to add, 1 to change, 3 to destroy."
        result = processor_obj.extract_plan_summary(text)
        
        assert result is not None
        assert result['to_add'] == 2
        assert result['to_change'] == 1
        assert result['to_destroy'] == 3
    
    def test_extract_plan_summary_not_found(self, mock_secrets, processing_config):
        """Test plan summary not found"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "No plan summary here"
        result = processor_obj.extract_plan_summary(text)
        
        assert result is None


class TestApplyResultExtraction:
    """Test apply result extraction"""
    
    def test_extract_apply_result_success(self, mock_secrets, processing_config):
        """Test successful apply result extraction"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "Apply complete! Resources: 5 destroyed"
        result = processor_obj.extract_apply_result(text)
        
        assert result is not None
        assert result['status'] == 'success'
        assert result['resources_destroyed'] == 5
    
    def test_extract_apply_result_failed(self, mock_secrets, processing_config):
        """Test failed apply result extraction"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "Error: Failed to apply changes"
        result = processor_obj.extract_apply_result(text)
        
        assert result is not None
        assert result['status'] == 'failed'
    
    def test_extract_apply_result_not_found(self, mock_secrets, processing_config):
        """Test apply result not found"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "No apply result here"
        result = processor_obj.extract_apply_result(text)
        
        assert result is None


class TestErrorExtraction:
    """Test error extraction"""
    
    def test_extract_errors(self, mock_secrets, processing_config):
        """Test error extraction"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "Error: Resource not found\nDetails: The resource does not exist"
        result = processor_obj.extract_errors(text)
        
        assert result is not None
        assert 'Error' in result
    
    def test_extract_errors_not_found(self, mock_secrets, processing_config):
        """Test no errors found"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "No errors here"
        result = processor_obj.extract_errors(text)
        
        assert result is None


class TestHighRiskDetection:
    """Test high-risk resource detection"""
    
    def test_has_high_risk_resources(self, mock_secrets, processing_config):
        """Test high-risk resource detection"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "aws_db_instance.example will be destroyed"
        plan_summary = {'to_add': 0, 'to_change': 0, 'to_destroy': 1}
        
        result = processor_obj.has_high_risk_resources(text, plan_summary)
        
        assert result is True
    
    def test_no_high_risk_resources(self, mock_secrets, processing_config):
        """Test no high-risk resources"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "aws_s3_bucket.example will be created"
        plan_summary = {'to_add': 1, 'to_change': 0, 'to_destroy': 0}
        
        result = processor_obj.has_high_risk_resources(text, plan_summary)
        
        assert result is False
    
    def test_high_risk_only_on_changes(self, mock_secrets, processing_config):
        """Test high-risk only checked on changes/destroys"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "aws_db_instance.example will be destroyed"
        plan_summary = {'to_add': 0, 'to_change': 0, 'to_destroy': 0}
        
        result = processor_obj.has_high_risk_resources(text, plan_summary)
        
        assert result is False


class TestResourceCounting:
    """Test resource counting"""
    
    def test_count_resources(self, mock_secrets, processing_config):
        """Test resource counting"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = """
        aws_instance.example1
        aws_instance.example2
        aws_vpc.example
        """
        
        result = processor_obj.count_resources(text)
        
        assert 'AWS Instance' in result
        assert result['AWS Instance'] == 2
        assert 'AWS VPC' in result
    
    def test_count_resources_empty(self, mock_secrets, processing_config):
        """Test resource counting with no resources"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "No resources here"
        result = processor_obj.count_resources(text)
        
        assert isinstance(result, dict)


class TestMessageFormatting:
    """Test message formatting functions"""
    
    def test_format_plan_with_regex(self, mock_secrets, processing_config):
        """Test plan formatting with regex"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        plan_summary = {'to_add': 0, 'to_change': 0, 'to_destroy': 5}
        text = "aws_instance.example will be destroyed"
        
        result = processor_obj.format_plan_with_regex(plan_summary, text)
        
        assert len(result) > 0
        assert 'Destroy Plan' in result[0]
    
    def test_format_plan_with_risk_analysis(self, mock_secrets, processing_config):
        """Test plan formatting with risk analysis"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        plan_summary = {'to_add': 0, 'to_change': 0, 'to_destroy': 5}
        risk_analysis = "High risk: Destroying critical resources"
        text = "aws_instance.example will be destroyed"
        
        result = processor_obj.format_plan_with_risk_analysis(plan_summary, risk_analysis, text)
        
        assert len(result) > 0
        assert 'Risk Analysis' in result[0]
    
    def test_format_apply_result(self, mock_secrets, processing_config):
        """Test apply result formatting"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        apply_result = {'status': 'success', 'resources_destroyed': 5}
        text = "Apply complete!"
        
        result = processor_obj.format_apply_result(apply_result, text)
        
        assert len(result) > 0
        assert 'Destroy Apply' in result[0]
    
    def test_format_status_with_regex(self, mock_secrets, processing_config):
        """Test status formatting"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "aws_instance.example"
        result = processor_obj.format_status_with_regex(text)
        
        assert len(result) > 0
        assert 'Terraform Status' in result[0]
    
    def test_format_error_summary(self, mock_secrets, processing_config):
        """Test error summary formatting"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        error_summary = "The resource was not found"
        result = processor_obj.format_error_summary(error_summary, 'status')
        
        assert len(result) > 0
        assert 'Error' in result[0]


class TestDuplicateRemoval:
    """Test duplicate section removal"""
    
    def test_remove_duplicate_sections(self, mock_secrets, processing_config):
        """Test duplicate section removal"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = """
        Terraform will destroy the following:
        - resource1
        - resource2
        
        Terraform will destroy the following:
        - resource1
        - resource2
        """
        
        result = processor_obj.remove_duplicate_sections(text)
        
        # Should have only one "Terraform will destroy" section
        assert result.count('Terraform will destroy') <= 1


class TestTelegramMessageWithButton:
    """Test Telegram message with button"""
    
    def test_send_telegram_message_with_button(self, mock_secrets, processing_config):
        """Test sending message with button"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch.object(processor_obj, 'send_telegram_message') as mock_send:
            mock_send.return_value = {'ok': True}
            
            result = processor_obj.send_telegram_message_with_button('123456789', 'Test message', 'destroy', 'test-project')
            
            assert result['ok'] is True
            mock_send.assert_called_once()
            # Check reply_markup was passed
            call_args = mock_send.call_args
            assert call_args[1]['reply_markup'] is not None
    
    def test_send_telegram_message_markdown_fallback(self, mock_secrets, processing_config):
        """Test Markdown parsing failure fallback"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch('processor.requests.post') as mock_post:
            # First call fails with 400 (Markdown error)
            mock_response1 = Mock()
            mock_response1.status_code = 400
            # Second call succeeds
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.json.return_value = {'ok': True}
            mock_response2.raise_for_status = Mock()
            mock_post.side_effect = [mock_response1, mock_response2]
            
            result = processor_obj.send_telegram_message('123456789', 'Test **message**')
            
            assert result['ok'] is True
            assert mock_post.call_count == 2  # First with Markdown, second without


class TestProcessOutputFlow:
    """Test process_output method flow for different commands"""
    
    def test_process_output_with_errors(self, mock_secrets, processing_config):
        """Test process_output with errors detected"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        error_output = "Error: Resource not found"
        
        with patch.object(processor_obj, 'extract_errors', return_value=error_output), \
             patch.object(processor_obj, 'summarize_error_with_ai', return_value="Error summary"), \
             patch.object(processor_obj, 'format_error_summary', return_value=["Error message"]), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[{'ok': True}]):
            
            result = processor_obj.process_output(error_output, 'status', '123456789')
            
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['success'] is True
    
    def test_process_output_destroy_with_high_risk(self, mock_secrets):
        """Test process_output for destroy command with high-risk resources"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        destroy_output = "Plan: 0 to add, 0 to change, 5 to destroy\naws_db_instance.example will be destroyed"
        
        with patch.object(processor_obj, 'extract_errors', return_value=None), \
             patch.object(processor_obj, 'extract_plan_summary', return_value={'to_add': 0, 'to_change': 0, 'to_destroy': 5}), \
             patch.object(processor_obj, 'has_high_risk_resources', return_value=True), \
             patch.object(processor_obj, 'analyze_risk_with_ai', return_value="High risk analysis"), \
             patch.object(processor_obj, 'format_plan_with_risk_analysis', return_value=["Plan with risk"]), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[{'ok': True}]):
            
            result = processor_obj.process_output(destroy_output, 'destroy', '123456789', project='test-project')
            
            assert result['statusCode'] == 200
    
    def test_process_output_destroy_low_risk(self, mock_secrets):
        """Test process_output for destroy command with low-risk resources"""
        config = processor.ProcessingConfig(enable_ai_processing=True)
        processor_obj = processor.TerraformOutputProcessor(config)
        
        destroy_output = "Plan: 0 to add, 0 to change, 2 to destroy\naws_s3_bucket.example will be destroyed"
        
        with patch.object(processor_obj, 'extract_errors', return_value=None), \
             patch.object(processor_obj, 'extract_plan_summary', return_value={'to_add': 0, 'to_change': 0, 'to_destroy': 2}), \
             patch.object(processor_obj, 'has_high_risk_resources', return_value=False), \
             patch.object(processor_obj, 'format_plan_with_regex', return_value=["Plan message"]), \
             patch.object(processor_obj, 'send_telegram_message_with_button', return_value={'ok': True}), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[]):
            
            result = processor_obj.process_output(destroy_output, 'destroy', '123456789', project='test-project')
            
            assert result['statusCode'] == 200
    
    def test_process_output_confirm_destroy_success(self, mock_secrets, processing_config):
        """Test process_output for confirm_destroy with success"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        apply_output = "Apply complete! Resources: 5 destroyed"
        
        with patch.object(processor_obj, 'extract_errors', return_value=None), \
             patch.object(processor_obj, 'extract_apply_result', return_value={'status': 'success', 'resources_destroyed': 5}), \
             patch.object(processor_obj, 'format_apply_result', return_value=["Success message"]), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[{'ok': True}]):
            
            result = processor_obj.process_output(apply_output, 'confirm_destroy', '123456789')
            
            assert result['statusCode'] == 200
    
    def test_process_output_confirm_destroy_failed(self, mock_secrets, processing_config):
        """Test process_output for confirm_destroy with failure"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        apply_output = "Error: Failed to apply"
        
        with patch.object(processor_obj, 'extract_errors', return_value="Error: Failed"), \
             patch.object(processor_obj, 'extract_apply_result', return_value={'status': 'failed'}), \
             patch.object(processor_obj, 'summarize_error_with_ai', return_value="Error summary"), \
             patch.object(processor_obj, 'format_error_summary', return_value=["Error message"]), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[{'ok': True}]):
            
            result = processor_obj.process_output(apply_output, 'confirm_destroy', '123456789')
            
            assert result['statusCode'] == 200
    
    def test_process_output_unknown_command(self, mock_secrets, processing_config):
        """Test process_output for unknown command"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        output = "Some output"
        
        with patch.object(processor_obj, 'extract_errors', return_value=None), \
             patch.object(processor_obj, 'process_simple', return_value=["Simple message"]), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[{'ok': True}]):
            
            result = processor_obj.process_output(output, 'unknown', '123456789')
            
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['processing_method'] == 'regex_only'
    
    def test_process_output_empty_messages(self, mock_secrets, processing_config):
        """Test process_output when split_message returns empty"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        with patch.object(processor_obj, 'extract_errors', return_value=None), \
             patch.object(processor_obj, 'format_status_with_regex', return_value=[]), \
             patch.object(processor_obj, 'send_telegram_messages', return_value=[]):
            
            result = processor_obj.process_output("test", 'status', '123456789')
            
            # Should handle gracefully
            assert result['statusCode'] == 200


class TestParseTerraformOutput:
    """Test parse_terraform_output method"""
    
    def test_parse_terraform_output_confirm_destroy(self, mock_secrets, processing_config):
        """Test parsing confirm_destroy output"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "Apply complete! Resources: 5 destroyed"
        result = processor_obj.parse_terraform_output(text, 'confirm_destroy')
        
        assert len(result) > 0
        assert 'Destruction completed' in result or 'Resources Destroyed' in result
    
    def test_parse_terraform_output_with_resource_counts(self, mock_secrets, processing_config):
        """Test parsing output with resource counts"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        text = "aws_instance.example1\naws_instance.example2"
        result = processor_obj.parse_terraform_output(text, 'status')
        
        assert len(result) > 0


class TestSplitMessageEdgeCases:
    """Test split_message edge cases"""
    
    def test_split_message_empty(self, mock_secrets, processing_config):
        """Test splitting empty message"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        result = processor_obj.split_message("")
        
        assert result == []
    
    def test_split_message_whitespace_only(self, mock_secrets, processing_config):
        """Test splitting whitespace-only message"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        result = processor_obj.split_message("   \n\n   ")
        
        assert result == []
    
    def test_split_message_single_long_line(self, mock_secrets, processing_config):
        """Test splitting single very long line"""
        processor_obj = processor.TerraformOutputProcessor(processing_config)
        
        long_line = "x" * 5000
        result = processor_obj.split_message(long_line)
        
        assert len(result) > 0
        for msg in result:
            assert len(msg) <= processing_config.max_message_length + 100
