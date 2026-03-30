all: clean sdist

format:
	ruff format .
test:
	python -m unittest discover -s tests
clean:
	rm -rf dist build venv
	sdist bdist_wheel
pre-commit:
	pre-commit install
develop: clean
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt
	venv/bin/pip install -r requirements.dev.txt
	venv/bin/pre-commit install
