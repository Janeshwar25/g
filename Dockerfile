# Use Python 3.11 slim image as base
FROM docker.repo1.uhc.com/cirrus/com.optum.cirrus.docker/golden-python-base:1.0.7

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Copy requirements file first for better caching
COPY requirements.txt .

# Switch to root for installations, fix permissions and install Python dependencies
USER root
RUN chmod 644 requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Fix permissions for all files
RUN chown -R $(whoami):$(whoami) /app && \
    chmod -R 755 /app

# Create necessary directories
RUN mkdir -p documents

# Make run script executable and fix line endings
RUN chmod +x run.sh && \
    dos2unix run.sh 2>/dev/null || true

# Expose only port 8080
EXPOSE 8080

# Override any existing entrypoint and run only Streamlit on port 8080
ENTRYPOINT []
CMD ["sh", "-c", "python3 -m uvicorn app.routes:app --host 127.0.0.1 --port 8000 & sleep 5 && python3 -m streamlit run app/app.py --server.port 8080 --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false"]