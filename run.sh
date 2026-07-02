#!/bin/bash

# Load configuration values with defaults
API_HOST=${API_HOST:-127.0.0.1}
API_PORT=${API_PORT:-8000}
STREAMLIT_HOST=${STREAMLIT_HOST:-0.0.0.0}
STREAMLIT_PORT=${STREAMLIT_PORT:-8080}

#Start FastAPI on localhost:8000
python3 -m uvicorn app.routes:app --host $API_HOST --port $API_PORT --reload &
#Wait a bit for backend to start
sleep 5
#Start Streamlit UI on 0.0.0.0:8080
python3 -m streamlit run app/app.py --server.port $STREAMLIT_PORT --server.address $STREAMLIT_HOST --server.enableCORS false --server.enableXsrfProtection false
