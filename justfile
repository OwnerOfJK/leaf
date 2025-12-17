claude:
  #!/usr/bin/env bash
  PROMPT=$(cat <<'EOF'
    When modifying or writing code, always provide a clean, modern rewrite.
    Do not introduce tests, or documentation unless requested.
    Do not change existing code without direct approval.
    After code changes, you may suggest running "just build" but never restart or manage services; ask the user first.
    Do not fully implement solutions without prior discussion and alignment.
    Keep responses concise; provide code examples only when explicitly asked.
    Never reference git, version control actions, or commits.
    Do not estimate timelines, effort, or percentage completion; do not suggest phases or delivery planning.
    Avoid quick or temporary fixes; recommend robust, maintainable solutions.
    If a request cannot be fulfilled under these rules, clearly explain why.
    During debugging tasks, propose visibility improvements (logging/tracing) before modifying logic and confirm with the user before adding instrumentation.
    Use a neutral, direct tone; avoid praise, enthusiasm, or positive judgments about ideas or work quality.
    Focus on realism: highlight trade-offs, limitations, and risks rather than optimism or assumptions.
    Never assess or imply "closeness to done" (no progress percentages, no hour estimates, no "almost complete").
    Do not volunteer to implement missing functionality; clearly separate analysis from action.
  EOF
  )

  clear && claude \
    --append-system-prompt "$PROMPT"

# Start databases only
start-db:
    docker compose up -d postgres redis

# Start backend API server
start-backend:
    cd backend && source .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0

# Start Celery worker
start-worker:
    cd backend && source .venv/bin/activate && celery -A app.workers.celery_app worker --loglevel=info

# Start frontend dev server
start-frontend:
    cd frontend && npm run dev

# Start all services
start:
    #!/usr/bin/env bash
    # Clean previous instances
    echo "Cleaning previous containers and processes..."
    docker compose down
    pkill -f "uvicorn main:app" || true
    pkill -f "celery.*worker" || true
    pkill -f "next-server" || true

    echo "Starting databases..."
    just start-db
    echo "Waiting for databases to be ready..."
    sleep 3

    echo "Starting services (Ctrl+C to stop all)..."

    cleanup() {
        echo ""
        echo "Stopping services..."
        pkill -f "uvicorn main:app" || true
        pkill -f "celery.*worker" || true
        pkill -f "next-server" || true
        echo "All services stopped."
        exit 0
    }

    trap cleanup SIGINT SIGTERM

    just start-backend & \
    just start-worker & \
    just start-frontend & \
    wait