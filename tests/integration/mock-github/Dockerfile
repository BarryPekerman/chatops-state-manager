FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Flask and requests
RUN pip install --no-cache-dir Flask==3.0.0 requests==2.31.0

# Copy mock server
COPY app.py /app/

# Expose port
EXPOSE 5000

# Run the server
CMD ["python", "app.py"]





