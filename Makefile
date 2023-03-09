all: clean sdist

format:
	black main.py && isort --profile black main.py

develop: clean
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt
	venv/bin/pip install -r requirements.dev.txt
	venv/bin/pre-commit install
