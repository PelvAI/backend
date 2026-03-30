FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install pdm

# Copy project files
COPY pyproject.toml pdm.lock* ./

# Install dependencies
RUN pdm install --check --prod --no-editable

# Copy application code
COPY . .

# Add local packages to python path
ENV PYTHONPATH=/app/__pypackages__/3.11/lib:/app

# Expose port
EXPOSE 8000

# Command is overridden in docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
