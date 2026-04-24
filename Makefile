.PHONY: dev test lint format install clean

# Development server with auto-reload
dev:
	cd backend && python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 8080

# Development server without auth (for local testing)
dev-noauth:
	cd backend && python3 app.py --no-auth

# Run tests
test:
	cd backend && python3 -m pytest ../tests/ -v

# Run tests with coverage
test-cov:
	cd backend && python3 -m pytest ../tests/ -v --cov=. --cov-report=term-missing

# Lint with ruff
lint:
	ruff check backend/ --select=E,W,F --ignore=E501

# Format with ruff
format:
	ruff format backend/

# Install dependencies
install:
	pip3 install -r backend/requirements.txt

# Clean generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
