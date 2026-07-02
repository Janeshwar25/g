# Docker Setup for Project Plan Builder

This project has been dockerized to make it easy to run and test in a containerized environment.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

### Option 1: Using Docker Compose (Recommended)

1. **Build and run the application:**
   ```bash
   docker-compose up --build
   ```

2. **Access the applications:**
   - Streamlit UI: http://localhost:8501
   - FastAPI Backend: http://localhost:8080
   - API Documentation: http://localhost:8080/docs

3. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Option 2: Using Docker directly

1. **Build the Docker image:**
   ```bash
   docker build -t project-plan-builder .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8080:8080 -p 8501:8501 \
     -v $(pwd)/documents:/app/documents \
     -v $(pwd)/upload:/app/upload \
     project-plan-builder
   ```

## Development Setup

For development with hot-reload and file watching:

```bash
docker-compose -f docker-compose.dev.yml up --build
```

This will:
- Mount your local code into the container
- Enable hot-reload for both FastAPI and Streamlit
- Sync changes automatically

## File Structure

The Docker setup includes:
- `Dockerfile`: Main container definition
- `docker-compose.yml`: Production configuration
- `docker-compose.dev.yml`: Development configuration with hot-reload
- `.dockerignore`: Files to exclude from Docker context

## Ports

- **8080**: FastAPI backend server
- **8501**: Streamlit frontend server

## Volume Mounts

The following directories are mounted as volumes to persist data:
- `./documents`: For plan metadata and generated files
- `./upload`: For Smartsheet export functionality

## Troubleshooting

1. **Port conflicts**: If ports 8080 or 8501 are already in use, modify the port mappings in `docker-compose.yml`

2. **Permission issues**: If you encounter permission issues with mounted volumes, try:
   ```bash
   sudo chown -R $(whoami):$(whoami) documents upload
   ```

3. **Container logs**: To view application logs:
   ```bash
   docker-compose logs -f
   ```

4. **Rebuild after changes**: If you make changes to requirements.txt or other configuration:
   ```bash
   docker-compose up --build
   ```

## Environment Variables

The container sets the following environment variables:
- `PYTHONPATH=/app`: Ensures proper Python module resolution
- `PYTHONUNBUFFERED=1`: Enables real-time logging output

## Health Check

The production setup includes a health check that verifies the FastAPI service is running properly.

## Stopping the Application

To stop and remove containers:
```bash
docker-compose down
```

To also remove volumes:
```bash
docker-compose down -v
```