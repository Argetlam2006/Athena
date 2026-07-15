# Use Python 3.11 slim for a lightweight footprint
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

# Create the non-root user and app directory
RUN groupadd -r athena && useradd -r -g athena athena
WORKDIR $APP_HOME

# Install system dependencies if required (e.g. for building C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . $APP_HOME

# Change ownership to the non-root user
RUN chown -R athena:athena $APP_HOME

# Switch to non-root user
USER athena

# Expose Streamlit's default port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Command to run the application
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
