all: clean sdist

format:
	ruff format .

develop: clean
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt
	venv/bin/pip install -r requirements.dev.txt
	venv/bin/pre-commit install
