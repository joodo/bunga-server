#!/bin/bash

# --- Configuration ---
APP_NAME="bunga"
WEB_PID="web.pid"
WORKER_PID="worker.pid"
DEFAULT_SERVER_PORT="8000"
BIND_HOST="0.0.0.0"

# --- Functions ---

resolve_server_port() {
    local server_port
    server_port=$(uv run python -c "from bunga.local_settings import SERVER_PORT; print(int(SERVER_PORT))" 2>/dev/null)

    if [ -z "$server_port" ]; then
        echo "WARNING: SERVER_PORT not found in bunga/local_settings.py. Use default ${DEFAULT_SERVER_PORT}." >&2
        server_port="$DEFAULT_SERVER_PORT"
    fi

    echo "$server_port"
}

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
    local server_port
    server_port=$(resolve_server_port)

    # 1. Start Gunicorn (ASGI)
    # Using uvicorn worker to handle WebSocket and HTTP
    if ! uv run gunicorn --daemon \
        --bind "${BIND_HOST}:${server_port}" \
        -k uvicorn.workers.UvicornWorker \
        --pid $WEB_PID \
        $APP_NAME.asgi:application; then
        echo "Failed to start Gunicorn."
        return 1
    fi
    echo "Gunicorn (ASGI) started at ${BIND_HOST}:${server_port}."

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

    stop_services || return 1
    
    echo "Syncing dependencies with uv..."
    uv sync --frozen || return 1
    
    echo "Running database migrations..."
    uv run python manage.py migrate || return 1
    
    echo "Collecting static files for WhiteNoise..."
    uv run python manage.py collectstatic --noinput || return 1
    
    start_services || return 1

    # First-time initialization check
    if [ ! -f .initialized ]; then
        echo "------------------------------------------------"
        echo "💡 FIRST RUN DETECTED!"
        echo "Creating superuser for Django Admin..."
        # This will be interactive
        if uv run python manage.py createsuperuser; then
            touch .initialized
        else
            echo "❌ Superuser creation failed. Skip creating .initialized."
            return 1
        fi
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
