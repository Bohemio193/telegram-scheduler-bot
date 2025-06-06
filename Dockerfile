FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY telegram-bot-requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY keep_alive.py .
COPY mensajes.json .
COPY estadisticas.json .

# Create directories for data persistence
RUN mkdir -p /app/data

# Expose port for keep-alive service
EXPOSE 8080

# Run the bot
CMD ["python", "main.py"]