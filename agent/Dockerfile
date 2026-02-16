# Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY agent/ ./agent/
COPY config/ ./config/

# Create non-root user for security
RUN useradd -m -u 1000 agent && \
    chown -R agent:agent /app

USER agent

# Run agent
CMD ["python", "-m", "agent.main"]
