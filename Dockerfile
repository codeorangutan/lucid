# Use the official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y wget gnupg2 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 libgtk-3-0 libxss1 libxtst6 fonts-liberation libappindicator3-1 lsb-release xdg-utils && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps

# Copy project files
COPY . .

# Default command: run pytest to check environment
CMD ["pytest", "tests/test_environment.py"]
