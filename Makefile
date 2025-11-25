.PHONY: help install dev run clean setup

# Variables
PYTHON := python3.10
VENV := venv
VENV_BIN := $(VENV)/bin
PYTHON_VENV := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
APP := app.py

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Create virtual environment and install dependencies
	@echo "🔧 Setting up virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "📦 Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅ Setup complete! Don't forget to create a .env file with your OPENAI_API_KEY"

install: ## Install dependencies (assumes venv exists)
	@echo "📦 Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

dev: ## Run the app with hot reloading (watches for file changes)
	@echo "🔥 Starting app with hot reloading..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ ! -f ".env" ]; then \
		echo "⚠️  Warning: .env file not found. Make sure to create it with your OPENAI_API_KEY"; \
	fi
	$(VENV_BIN)/watchmedo auto-restart \
		--patterns="*.py" \
		--recursive \
		--directory=. \
		-- \
		$(PYTHON_VENV) $(APP)

run: ## Run the app normally (without hot reloading)
	@echo "🚀 Starting app..."
	@if [ ! -d "$(VENV)" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ ! -f ".env" ]; then \
		echo "⚠️  Warning: .env file not found. Make sure to create it with your OPENAI_API_KEY"; \
	fi
	$(PYTHON_VENV) $(APP)

clean: ## Remove virtual environment and cache files
	@echo "🧹 Cleaning up..."
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	@echo "✅ Clean complete"

check-env: ## Check if .env file exists and has API key
	@if [ ! -f ".env" ]; then \
		echo "❌ .env file not found!"; \
		echo "Create it with: echo 'OPENAI_API_KEY=your_key_here' > .env"; \
		exit 1; \
	fi
	@grep -q "OPENAI_API_KEY" .env || (echo "❌ OPENAI_API_KEY not found in .env" && exit 1)
	@echo "✅ .env file looks good"

