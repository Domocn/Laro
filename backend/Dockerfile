FROM python:3.11-slim

WORKDIR /app

# Build argument for version (passed from CI/CD or docker-compose)
ARG APP_VERSION=0.0.0-dev
ENV APP_VERSION=$APP_VERSION

# Install system dependencies (curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
