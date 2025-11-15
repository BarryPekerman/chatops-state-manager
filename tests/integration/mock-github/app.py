"""
Mock GitHub Actions server for integration testing
Simulates GitHub repository_dispatch webhook endpoint
"""
from flask import Flask, request, jsonify
import logging
import time
from collections import deque

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store received dispatches for verification
received_dispatches = deque(maxlen=100)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


@app.route('/repos/<owner>/<repo>/dispatches', methods=['POST'])
def repository_dispatch(owner, repo):
    """
    Mock GitHub repository_dispatch endpoint
    Simulates triggering a GitHub Actions workflow
    """
    try:
        # Log the request
        logger.info(f"Received dispatch for {owner}/{repo}")

        # Validate authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('token '):
            return jsonify({'error': 'Unauthorized'}), 401

        # Parse payload
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'Invalid payload'}), 400

        event_type = payload.get('event_type')
        client_payload = payload.get('client_payload', {})

        logger.info(f"Event type: {event_type}")
        logger.info(f"Client payload: {client_payload}")

        # Store for verification
        received_dispatches.append({
            'timestamp': time.time(),
            'owner': owner,
            'repo': repo,
            'event_type': event_type,
            'client_payload': client_payload,
            'headers': dict(request.headers)
        })

        # Simulate GitHub's 204 No Content response
        return '', 204

    except Exception as e:
        logger.error(f"Error processing dispatch: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/test/dispatches', methods=['GET'])
def get_dispatches():
    """
    Test endpoint to retrieve received dispatches
    Used by integration tests to verify behavior
    """
    return jsonify({
        'count': len(received_dispatches),
        'dispatches': list(received_dispatches)
    }), 200


@app.route('/test/dispatches', methods=['DELETE'])
def clear_dispatches():
    """Clear all received dispatches"""
    received_dispatches.clear()
    return jsonify({'message': 'Cleared'}), 200


@app.route('/test/simulate-callback', methods=['POST'])
def simulate_callback():
    """
    Simulate GitHub Actions workflow completion callback
    Sends a callback to the webhook handler as if the workflow completed
    """
    try:
        payload = request.get_json()
        callback_url = payload.get('callback_url')
        chat_id = payload.get('chat_id')
        command = payload.get('command', 'status')
        raw_output = payload.get('raw_output', 'Mock Terraform output')

        if not callback_url or not chat_id:
            return jsonify({'error': 'Missing required fields'}), 400

        # Simulate sending callback
        import requests
        callback_payload = {
            'callback': True,
            'chat_id': chat_id,
            'command': command,
            'run_id': f'test-run-{int(time.time())}',
            'raw_output': raw_output
        }

        response = requests.post(callback_url, json=callback_payload, timeout=10)

        return jsonify({
            'message': 'Callback sent',
            'status_code': response.status_code,
            'response': response.text
        }), 200

    except Exception as e:
        logger.error(f"Error simulating callback: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
