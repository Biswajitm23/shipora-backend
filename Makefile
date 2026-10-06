# Shipora backend: native development (no Docker).
PY      := .venv/bin/python
MANAGE  := $(PY) manage.py

.PHONY: install migrate test lint run shell

install:            ## create the venv and install dependencies
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip --quiet
	.venv/bin/pip install -r requirements.txt

migrate:            ## apply database migrations
	$(MANAGE) migrate

test:               ## run the test suite (make test ARGS=apps/accounts for one app)
	.venv/bin/pytest $(ARGS)

lint:               ## ruff check + format check
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

run:                ## serve the API at http://localhost:8000/api/
	$(MANAGE) runserver

shell:              ## Django shell
	$(MANAGE) shell
