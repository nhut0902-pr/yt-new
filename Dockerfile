FROM python:3.10-slim

# Install curl, Node.js (needed for yt-dlp signature solver)
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code files
COPY . .

# Port that Render expects (Render sets PORT environment variable, defaulting to 10000)
EXPOSE 10000

# Run with Gunicorn bound to 0.0.0.0:10000
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
