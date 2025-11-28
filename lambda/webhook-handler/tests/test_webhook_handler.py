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

def create_response(status_code, body):
    """Helper to match create_response signature"""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body) if isinstance(body, dict) else body
    }


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

    def test_select_command(self, mock_env, mock_secrets, telegram_message_event):
        """Test /select command shows project selection menu"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 123456789, 'username': 'testuser'},
                'chat': {'id': 123456789},
                'text': '/select'
            }
        })

        with patch('webhook_handler.get_project_registry') as mock_registry, \
             patch('webhook_handler.send_telegram_message') as mock_send:
            mock_registry.return_value = {
                'projects': {
                    'test-project': {
                        'enabled': True,
                        'backend_bucket': 'test-bucket',
                        'backend_key': 'test-key',
                        'region': 'us-east-1',
                        'workspace': 'default'
                    }
                }
            }

            response = webhook_handler.lambda_handler(telegram_message_event, None)

            assert response['statusCode'] == 200
            mock_send.assert_called_once()

    def test_list_command(self, mock_env, mock_secrets, telegram_message_event):
        """Test /list command lists projects"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 123456789, 'username': 'testuser'},
                'chat': {'id': 123456789},
                'text': '/list'
            }
        })

        with patch('webhook_handler.get_project_registry') as mock_registry, \
             patch('webhook_handler.send_telegram_message') as mock_send:
            mock_registry.return_value = {
                'projects': {
                    'test-project': {
                        'enabled': True,
                        'backend_bucket': 'test-bucket',
                        'backend_key': 'test-key',
                        'region': 'us-east-1',
                        'workspace': 'default'
                    }
                }
            }

            response = webhook_handler.lambda_handler(telegram_message_event, None)

            assert response['statusCode'] == 200
            mock_send.assert_called_once()

    def test_callback_query_status(self, mock_env, mock_secrets):
        """Test callback query for status command"""
        callback_event = {
            'body': json.dumps({
                'callback_query': {
                    'id': 'query123',
                    'from': {'id': 123456789, 'username': 'testuser'},
                    'message': {
                        'chat': {'id': 123456789}
                    },
                    'data': 'status:test-project'
                }
            })
        }

        with patch('webhook_handler.trigger_github_workflow') as mock_trigger, \
             patch('webhook_handler.answer_callback_query') as mock_answer:
            mock_trigger.return_value = {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'})
            }

            response = webhook_handler.lambda_handler(callback_event, None)

            assert response['statusCode'] == 200
            mock_trigger.assert_called_once_with('status', 123456789, project='test-project')

    def test_callback_query_destroy(self, mock_env, mock_secrets):
        """Test callback query for destroy command"""
        callback_event = {
            'body': json.dumps({
                'callback_query': {
                    'id': 'query123',
                    'from': {'id': 123456789, 'username': 'testuser'},
                    'message': {
                        'chat': {'id': 123456789}
                    },
                    'data': 'destroy:test-project'
                }
            })
        }

        with patch('webhook_handler.trigger_github_workflow') as mock_trigger, \
             patch('webhook_handler.answer_callback_query') as mock_answer:
            mock_trigger.return_value = {
                'statusCode': 200,
                'body': json.dumps({'message': 'success'})
            }

            response = webhook_handler.lambda_handler(callback_event, None)

            assert response['statusCode'] == 200
            mock_trigger.assert_called_once_with('destroy', 123456789, project='test-project')

    def test_unauthorized_chat_id(self, mock_env, mock_secrets, telegram_message_event):
        """Test unauthorized chat ID rejection"""
        telegram_message_event['body'] = json.dumps({
            'message': {
                'from': {'id': 999999999, 'username': 'hacker'},
                'chat': {'id': 999999999},
                'text': '/select'
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
                response = webhook_handler.trigger_github_workflow('confirm_destroy', 123456789, project='test-project', token='token123')

                assert response['statusCode'] == 200

                # Verify token in payload
                call_args = mock_post.call_args
                payload = call_args[1]['json']
                assert payload['client_payload']['token'] == 'token123'
                assert payload['client_payload']['project'] == 'test-project'

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
        """Test destroy command feedback with project"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            webhook_handler.send_telegram_feedback(123456789, 'destroy', 'test-project')

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert 'Destroy Plan' in payload['text']
            assert 'test-project' in payload['text']


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

        with patch('webhook_handler.send_telegram_message_direct') as mock_send:
            # Configure mock to return proper response
            mock_send.return_value = {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Callback processed, message sent to Telegram'})
            }
            response = webhook_handler.lambda_handler(callback_event, None)

            assert response['statusCode'] == 200
            mock_send.assert_called_once()


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
        # Should handle gracefully - returns 500 for invalid request format
        assert response['statusCode'] == 500


class TestProjectRegistry:
    """Test project registry retrieval"""

    def test_get_project_registry_success(self, mock_env, mock_secrets):
        """Test successful project registry retrieval"""
        with patch.dict(os.environ, {'PROJECT_REGISTRY_SECRET_ARN': 'chatops/project-registry'}):
            mock_secrets.create_secret(
                Name='chatops/project-registry',
                SecretString=json.dumps({
                    'projects': {
                        'test-project': {
                            'enabled': True,
                            'backend_bucket': 'test-bucket',
                            'backend_key': 'test-key'
                        }
                    }
                })
            )

            registry = webhook_handler.get_project_registry()
            assert registry is not None
            assert 'projects' in registry
            assert 'test-project' in registry['projects']

    def test_get_project_registry_arn_with_suffix(self, mock_env, mock_secrets):
        """Test ARN parsing with 6-character suffix"""
        with patch.dict(os.environ, {'PROJECT_REGISTRY_SECRET_ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:chatops/project-registry-abc123'}):
            mock_secrets.create_secret(
                Name='chatops/project-registry',
                SecretString=json.dumps({'projects': {}})
            )

            registry = webhook_handler.get_project_registry()
            assert registry is not None

    def test_get_project_registry_missing_env(self, mock_env, mock_secrets):
        """Test missing PROJECT_REGISTRY_SECRET_ARN"""
        with patch.dict(os.environ, {}, clear=True):
            registry = webhook_handler.get_project_registry()
            assert registry is None

    def test_get_project_registry_secret_not_found(self, mock_env, mock_secrets):
        """Test registry secret not found"""
        with patch.dict(os.environ, {'PROJECT_REGISTRY_SECRET_ARN': 'nonexistent-secret'}):
            registry = webhook_handler.get_project_registry()
            assert registry is None


class TestTelegramWebhookValidation:
    """Test Telegram webhook signature validation"""

    def test_validate_telegram_webhook_success(self, mock_secrets):
        """Test successful webhook validation"""
        headers = {'x-telegram-bot-api-secret-token': 'test-secret-token'}
        body = {}

        result = webhook_handler.validate_telegram_webhook(body, headers)
        assert result is True

    def test_validate_telegram_webhook_missing_signature(self, mock_secrets):
        """Test missing signature in headers"""
        headers = {}
        body = {}

        result = webhook_handler.validate_telegram_webhook(body, headers)
        assert result is False

    def test_validate_telegram_webhook_invalid_signature(self, mock_secrets):
        """Test invalid signature"""
        headers = {'x-telegram-bot-api-secret-token': 'wrong-token'}
        body = {}

        result = webhook_handler.validate_telegram_webhook(body, headers)
        assert result is False

    def test_validate_telegram_webhook_missing_secret_token(self, mock_secrets):
        """Test missing secret token in secrets"""
        # Remove telegram_secret_token from secrets
        mock_secrets.update_secret(
            SecretId='chatops/secrets',
            SecretString=json.dumps({
                'github_token': 'ghp_test_token_12345',
                'telegram_bot_token': '123456:ABC-DEF'
            })
        )

        headers = {'x-telegram-bot-api-secret-token': 'test-token'}
        body = {}

        result = webhook_handler.validate_telegram_webhook(body, headers)
        assert result is False


class TestCallbackHandling:
    """Test callback handling edge cases"""

    def test_handle_callback_missing_chat_id(self, mock_env, mock_secrets):
        """Test callback with missing chat_id"""
        body = {
            'callback': True,
            'command': 'status',
            'raw_output': 'test output'
        }

        response = webhook_handler.handle_callback(body)
        assert response['statusCode'] == 400
        body_data = json.loads(response['body'])
        assert 'Missing chat_id' in body_data['error']

    def test_handle_callback_ai_processor_failure(self, mock_env, mock_secrets):
        """Test AI processor invocation failure"""
        with patch.dict(os.environ, {'AI_PROCESSOR_FUNCTION_ARN': 'arn:aws:lambda:us-east-1:123456789012:function:ai-processor'}):
            body = {
                'callback': True,
                'chat_id': 123456789,
                'command': 'destroy',
                'raw_output': 'test output'
            }

            with patch('webhook_handler.lambda_client.invoke') as mock_invoke:
                mock_invoke.side_effect = Exception('Lambda invocation failed')

                with patch('webhook_handler.send_telegram_message_direct') as mock_send:
                    mock_send.return_value = create_response(200, {'message': 'sent'})
                    response = webhook_handler.handle_callback(body)

                    # Should fallback to direct message
                    mock_send.assert_called_once()

    def test_handle_callback_no_ai_processor(self, mock_env, mock_secrets):
        """Test callback without AI processor configured"""
        with patch.dict(os.environ, {'AI_PROCESSOR_FUNCTION_ARN': ''}):
            body = {
                'callback': True,
                'chat_id': 123456789,
                'command': 'destroy',
                'raw_output': 'test output'
            }

            with patch('webhook_handler.send_telegram_message_direct') as mock_send:
                mock_send.return_value = create_response(200, {'message': 'sent'})
                response = webhook_handler.handle_callback(body)

                mock_send.assert_called_once()


class TestAIProcessorInvocation:
    """Test AI processor Lambda invocation"""

    def test_invoke_ai_processor_success(self, mock_env, mock_secrets):
        """Test successful AI processor invocation"""
        with patch.dict(os.environ, {'AI_PROCESSOR_FUNCTION_ARN': 'arn:aws:lambda:us-east-1:123456789012:function:ai-processor'}):
            with patch('webhook_handler.lambda_client.invoke') as mock_invoke:
                mock_invoke.return_value = {'StatusCode': 202}

                response = webhook_handler.invoke_ai_processor(123456789, 'destroy', 'test output', 'run123', 'test-project')

                assert response['statusCode'] == 200
                mock_invoke.assert_called_once()

    def test_invoke_ai_processor_empty_arn(self, mock_env, mock_secrets):
        """Test with empty AI processor ARN"""
        with patch.dict(os.environ, {'AI_PROCESSOR_FUNCTION_ARN': ''}):
            with patch('webhook_handler.send_telegram_message_direct') as mock_send:
                mock_send.return_value = create_response(200, {'message': 'sent'})
                response = webhook_handler.invoke_ai_processor(123456789, 'destroy', 'test output')

                mock_send.assert_called_once()

    def test_invoke_ai_processor_failure_fallback(self, mock_env, mock_secrets):
        """Test AI processor failure with fallback"""
        with patch.dict(os.environ, {'AI_PROCESSOR_FUNCTION_ARN': 'arn:aws:lambda:us-east-1:123456789012:function:ai-processor'}):
            with patch('webhook_handler.lambda_client.invoke') as mock_invoke:
                mock_invoke.side_effect = Exception('Invocation failed')

                with patch('webhook_handler.send_telegram_message_direct') as mock_send:
                    mock_send.return_value = create_response(200, {'message': 'sent'})
                    response = webhook_handler.invoke_ai_processor(123456789, 'destroy', 'test output')

                    mock_send.assert_called_once()


class TestCallbackQueries:
    """Test callback query handling"""

    def test_callback_query_back_button(self, mock_env, mock_secrets):
        """Test back button callback"""
        callback_query = {
            'id': 'query123',
            'message': {'chat': {'id': 123456789}},
            'data': 'back'
        }

        with patch('webhook_handler.get_project_registry') as mock_registry, \
             patch('webhook_handler.answer_callback_query') as mock_answer, \
             patch('webhook_handler.show_project_selection_menu') as mock_show:
            mock_registry.return_value = {'projects': {'test-project': {'enabled': True}}}
            mock_show.return_value = create_response(200, {'message': 'shown'})

            response = webhook_handler.handle_callback_query(callback_query)
            assert response['statusCode'] == 200

    def test_callback_query_cancel(self, mock_env, mock_secrets):
        """Test cancel callback"""
        callback_query = {
            'id': 'query123',
            'message': {'chat': {'id': 123456789}},
            'data': 'cancel'
        }

        with patch('webhook_handler.answer_callback_query') as mock_answer, \
             patch('webhook_handler.send_telegram_message') as mock_send:
            response = webhook_handler.handle_callback_query(callback_query)
            assert response['statusCode'] == 200
            mock_send.assert_called_once()

    def test_callback_query_confirm_destroy(self, mock_env, mock_secrets):
        """Test confirm_destroy callback"""
        callback_query = {
            'id': 'query123',
            'message': {'chat': {'id': 123456789}},
            'data': 'confirm_destroy:test-project'
        }

        with patch('webhook_handler.answer_callback_query') as mock_answer, \
             patch('webhook_handler.trigger_github_workflow') as mock_trigger:
            mock_trigger.return_value = create_response(200, {'message': 'triggered'})
            response = webhook_handler.handle_callback_query(callback_query)
            assert response['statusCode'] == 200
            mock_trigger.assert_called_once_with('confirm_destroy', 123456789, project='test-project')

    def test_callback_query_invalid_data(self, mock_env, mock_secrets):
        """Test invalid callback data"""
        callback_query = {
            'id': 'query123',
            'message': {'chat': {'id': 123456789}},
            'data': 'invalid:data:format'
        }

        with patch('webhook_handler.answer_callback_query') as mock_answer:
            response = webhook_handler.handle_callback_query(callback_query)
            assert response['statusCode'] == 200  # Unknown command, but handled

    def test_callback_query_no_colon(self, mock_env, mock_secrets):
        """Test callback data without colon"""
        callback_query = {
            'id': 'query123',
            'message': {'chat': {'id': 123456789}},
            'data': 'invalidformat'
        }

        with patch('webhook_handler.answer_callback_query') as mock_answer:
            response = webhook_handler.handle_callback_query(callback_query)
            assert response['statusCode'] == 400


class TestUIFunctions:
    """Test UI helper functions"""

    def test_show_project_selection_menu(self, mock_env, mock_secrets):
        """Test project selection menu"""
        projects = {
            'project1': {'enabled': True},
            'project2': {'enabled': True},
            'project3': {'enabled': False}  # Should be skipped
        }

        with patch('webhook_handler.send_telegram_message') as mock_send:
            response = webhook_handler.show_project_selection_menu(123456789, projects)
            assert response['statusCode'] == 200
            mock_send.assert_called_once()
            # Check that reply_markup was passed (as third positional argument)
            call_args = mock_send.call_args
            assert len(call_args[0]) >= 3  # chat_id, message, reply_markup
            assert call_args[0][2] is not None  # reply_markup is the third positional arg
            assert 'inline_keyboard' in call_args[0][2]  # Verify it's a proper reply_markup dict

    def test_show_command_selection(self, mock_env, mock_secrets):
        """Test command selection menu"""
        with patch('webhook_handler.send_telegram_message') as mock_send:
            response = webhook_handler.show_command_selection(123456789, 'test-project')
            assert response['statusCode'] == 200
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert 'test-project' in call_args[0][1]  # Message contains project name

    def test_show_help(self, mock_env, mock_secrets):
        """Test help message"""
        with patch('webhook_handler.send_telegram_message') as mock_send:
            response = webhook_handler.show_help(123456789)
            assert response['statusCode'] == 200
            mock_send.assert_called_once()


class TestAnswerCallbackQuery:
    """Test callback query answering"""

    def test_answer_callback_query_success(self, mock_secrets):
        """Test successful callback query answer"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            webhook_handler.answer_callback_query('query123', 'Loading...')
            mock_post.assert_called_once()

    def test_answer_callback_query_with_alert(self, mock_secrets):
        """Test callback query answer with alert"""
        with patch('webhook_handler.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            webhook_handler.answer_callback_query('query123', 'Error!', show_alert=True)
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert payload['show_alert'] is True

    def test_answer_callback_query_no_token(self, mock_secrets):
        """Test callback query answer without bot token"""
        with patch('webhook_handler.get_telegram_bot_token', return_value=None):
            # Should not raise exception
            webhook_handler.answer_callback_query('query123', 'Test')


class TestBase64BodyParsing:
    """Test base64 encoded body parsing"""

    def test_base64_encoded_body(self, mock_env, mock_secrets):
        """Test parsing base64 encoded body"""
        import base64
        body_data = {'message': {'chat': {'id': 123456789}, 'text': '/help', 'from': {'id': 123456789, 'username': 'test'}}}
        encoded_body = base64.b64encode(json.dumps(body_data).encode('utf-8')).decode('utf-8')

        event = {
            'body': encoded_body,
            'isBase64Encoded': True,
            'headers': {}
        }

        with patch('webhook_handler.send_telegram_message') as mock_send:
            response = webhook_handler.lambda_handler(event, None)
            assert response['statusCode'] == 200
            mock_send.assert_called_once()
