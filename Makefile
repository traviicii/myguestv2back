.PHONY: lint test check

lint:
	ruff check app tests

test:
	pytest

check: lint test
