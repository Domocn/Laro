FROM python:3.11-slim

WORKDIR /app

# Build argument for version (passed from CI/CD or: --build-arg APP_VERSION=$(cat VERSION))
# Leave unset by default so runtime / VERSION file can supply the real value.
ARG APP_VERSION=
ENV APP_VERSION=$APP_VERSION

# curl = health checks; ffmpeg = social video → audio for Whisper import
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application (includes backend/VERSION when present)
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
