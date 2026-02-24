#!/bin/bash

# --- Configuration ---
APP_NAME="bunga"
WEB_PID="web.pid"
WORKER_PID="worker.pid"

# --- Functions ---

# Stop all running services
stop_services() {
    echo "Stopping $APP_NAME services..."
    
    if [ -f $WEB_PID ]; then
        kill $(cat $WEB_PID) && rm $WEB_PID
        echo "Stop Gunicorn: OK"
    else
        echo "Gunicorn is not running."
    fi

    if [ -f $WORKER_PID ]; then
        kill $(cat $WORKER_PID) && rm $WORKER_PID
        echo "Stop Presence Worker: OK"
    else
        echo "Presence Worker is not running."
    fi
}

# Start all services in background
start_services() {
    echo "Starting $APP_NAME services..."

    # 1. Start Gunicorn (ASGI)
    # Using uvicorn worker to handle WebSocket and HTTP
    uv run gunicorn --daemon \
        --bind 0.0.0.0:8000 \
        -k uvicorn.workers.UvicornWorker \
        --pid $WEB_PID \
        $APP_NAME.asgi:application
    echo "Gunicorn (ASGI) started at port 8000."

    # 2. Start Presence Worker
    # Running presence_worker for real-time synchronization
    nohup uv run python manage.py runworker presence_worker > worker.log 2>&1 &
    echo $! > $WORKER_PID
    echo "Presence Worker started."
}

# Deploy/Update the project
deploy_project() {
    echo "🚀 Starting Full Deployment/Update..."

    # --- Pre-deployment Check ---
    # Check if local_settings.py exists in the project subdirectory
    LOCAL_SETTINGS="bunga/local_settings.py"
    TEMPLATE_SETTINGS="bunga/local_settings.template.py"

    if [ ! -f "$LOCAL_SETTINGS" ]; then
        echo "--------------------------------------------------------"
        echo "❌ ERROR: $LOCAL_SETTINGS not found!"
        echo "Please copy the template to create your local settings:"
        echo "cp $TEMPLATE_SETTINGS $LOCAL_SETTINGS"
        echo "Then edit $LOCAL_SETTINGS with your production keys."
        echo "--------------------------------------------------------"
        exit 1 # Stop execution immediately
    fi
    # --- End of Check ---

    stop_services
    
    echo "Syncing dependencies with uv..."
    uv sync --frozen
    
    echo "Running database migrations..."
    uv run python manage.py migrate
    
    echo "Collecting static files for WhiteNoise..."
    uv run python manage.py collectstatic --noinput
    
    start_services

    # First-time initialization check
    if [ ! -f .initialized ]; then
        echo "------------------------------------------------"
        echo "💡 FIRST RUN DETECTED!"
        echo "Creating superuser for Django Admin..."
        # This will be interactive
        uv run python manage.py createsuperuser
        touch .initialized
    fi
    echo "✅ Deployment finished successfully."
}

# --- Command Router ---

case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        start_services
        ;;
    deploy)
        deploy_project
        ;;
    status)
        echo "Checking $APP_NAME status..."
        ps aux | grep -E "gunicorn|runworker" | grep -v grep
        ;;
    *)
        echo "Usage: ./manage.sh {start|stop|restart|deploy|status}"
        exit 1
        ;;
esac
