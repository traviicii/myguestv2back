.PHONY: lint test check smoke-remote

lint:
	ruff check app tests

test:
	pytest

check: lint test

smoke-remote:
	@test -n "$(BASE_URL)" || (echo "BASE_URL is required. Example: make smoke-remote BASE_URL=https://api.example.com/api/v1 TOKEN=\$$EXPO_PUBLIC_DEV_ID_TOKEN" && exit 1)
	@test -n "$(TOKEN)" || (echo "TOKEN is required. Example: make smoke-remote BASE_URL=https://api.example.com/api/v1 TOKEN=\$$EXPO_PUBLIC_DEV_ID_TOKEN" && exit 1)
	bash scripts/smoke_render_contract.sh "$(BASE_URL)" "$(TOKEN)"
