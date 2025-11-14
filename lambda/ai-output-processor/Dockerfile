# Dockerfile for ai-output-processor Lambda
FROM python:3.11-slim AS base

WORKDIR /opt/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Copy source files
COPY src/requirements.txt ./
COPY src/processor.py ./

# Install runtime dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -t .

# Test stage - runs unit tests and security scans
FROM base AS test

# Install test and security dependencies
RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    pytest-cov==4.1.0 \
    pytest-mock==3.12.0 \
    moto[secretsmanager]==4.2.10 \
    bandit==1.7.5 \
    pbr \
    safety==2.3.5

# Copy test files
COPY tests/ ./tests/

# Run security scans
RUN echo "Running security scans..." && \
    bandit -r processor.py -f json -o /tmp/bandit-report.json || true && \
    safety check --json || true

# Run unit tests with coverage
# Set AWS_REGION before running tests to avoid NoRegionError during module import
ENV AWS_REGION=us-east-1
RUN echo "Running unit tests..." && \
    pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html --cov-fail-under=70

# Build stage - creates ZIP artifact
FROM base AS build

# Remove test files and create clean ZIP
RUN zip -r /tmp/output_processor.zip . -x "*.pyc" "__pycache__/*" "tests/*" "*.dist-info/*"

# Runtime stage - for local testing with docker-compose
FROM python:3.11-slim AS runtime

WORKDIR /var/task

# Copy installed dependencies and source
COPY --from=base /opt/app /var/task/

# Set Lambda runtime interface if needed for local testing
ENV PYTHONUNBUFFERED=1

CMD ["processor.lambda_handler"]

# Artifact stage - for CI/CD artifact extraction
FROM scratch AS artifact
COPY --from=build /tmp/output_processor.zip /
