# Makefile to automate common tasks
.PHONY: install lint test run

# Install dependencies
install:
	pip install -r requirements.txt

# Run pre-commit hooks
lint:
	pre-commit run --all-files

# Run tests with pytest
test:
	pytest tests/

# Run the extract service on port 8000 with auto-reload
run:
	uvicorn app:app --reload --app-dir services/extract --port 8000
