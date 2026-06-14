$ErrorActionPreference = "Stop"

docker compose run --rm api alembic upgrade head

