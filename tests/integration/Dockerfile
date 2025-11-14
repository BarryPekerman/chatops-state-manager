FROM python:3.11-slim

WORKDIR /tests

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install test dependencies
RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    pytest-timeout==2.2.0 \
    requests==2.31.0 \
    boto3==1.34.10 \
    moto[secretsmanager]==4.2.10

# Copy integration tests
COPY test_*.py /tests/
COPY requirements.txt /tests/

# Default command runs pytest
CMD ["pytest", "-v", "--tb=short", "--color=yes"]





