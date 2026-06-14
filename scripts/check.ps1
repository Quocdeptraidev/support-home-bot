$ErrorActionPreference = "Stop"

docker compose run --rm api ruff check .
docker compose run --rm api ruff format --check .
docker compose run --rm api mypy app
docker compose run --rm api pytest
