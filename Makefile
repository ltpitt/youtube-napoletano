# You can override the venv name: make VENV=myenv install

.PHONY: help run install lint format clean ruff-check

VENV ?= .venv
.DEFAULT_GOAL := help

help:
	@echo "Common make targets:"
	@echo "  make install   - Create venv and install dependencies (default: VENV=$(VENV))"
	@echo "  make run       - Run the app using the venv"
	@echo "  make lint      - Lint code with ruff (requires venv and ruff)"
	@echo "  make format    - Format code with ruff (requires venv and ruff)"
	@echo "  make clean     - Remove venv and __pycache__ folders"
	@echo "  make help      - Show this help"
	@echo ""
	@echo "You can override the venv name: make VENV=myenv install"

run:
	@if [ ! -x "$(VENV)/bin/python" ]; then \
		echo "[ERROR] Virtual environment not found. Run 'make install' first, or set VENV variable."; \
		exit 1; \
	fi
	$(VENV)/bin/python youtube_napoletano.py

install:
	python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

lint: ruff-check
	$(VENV)/bin/ruff check --fix .

format: ruff-check
	$(VENV)/bin/ruff format .

ruff-check:
	@if [ ! -x "$(VENV)/bin/ruff" ]; then \
		if [ ! -x "$(VENV)/bin/python" ]; then \
			echo "[ERROR] Virtual environment not found. Run 'make install' first, or set VENV variable."; \
			exit 1; \
		fi; \
		echo "[INFO] Installing ruff..."; \
		$(VENV)/bin/pip install ruff; \
	fi

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf $(VENV)