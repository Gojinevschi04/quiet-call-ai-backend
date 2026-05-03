.PHONY: help db.make_migrations db.up db.down db.reset db.seed db.seed.demo black.run ruff.run mypy.run app.start app.stop app.logs app.logs.api app.logs.worker app.test ngrok.start

.DEFAULT_GOAL := help

help:
	@echo "RAG Web Application - Makefile"
	@echo "usage: make COMMAND"
	@echo ""
	@echo "Database Commands:"
	@echo "  db.make_migrations    Generate new migration file (requires m='message')"
	@echo "                        Example: make db.make_migrations m='Add user table'"
	@echo "  db.up                 Run all pending migrations"
	@echo "  db.down               Rollback all migrations to base"
	@echo "  db.reset              WIPE all data, re-run migrations, re-seed templates + demo"
	@echo "  db.seed               Seed dialog templates"
	@echo "  db.seed.demo          Seed demo users + tasks (for testing)"
	@echo ""
	@echo "Code Quality Commands:"
	@echo "  black.run             Format Python code with Black"
	@echo "  ruff.run              Lint and format code with Ruff"
	@echo "  mypy.run              Type check code with MyPy"
	@echo ""
	@echo "Application Commands:"
	@echo "  app.start             Build and start all containers (API, worker, Postgres)"
	@echo "  app.stop              Stop and remove all containers"
	@echo "  app.logs              Follow logs from all containers"
	@echo "  app.logs.api          Follow logs from quiet_call_api only"
	@echo "  app.logs.worker       Follow logs from quiet_call_worker only"
	@echo "  app.test              Run tests in Docker container"
	@echo ""
	@echo "Tunnel Commands:"
	@echo "  ngrok.start           Start ngrok tunnel on port 8000 with reserved domain"
	@echo "                        (required for Twilio webhooks during local development)"
	@echo ""
	@echo "Examples:"
	@echo "  make db.up                                    # Run migrations"
	@echo "  make db.make_migrations m='Add user table'   # Create migration"
	@echo "  make app.start                                # Start entire application"
	@echo "  make ngrok.start                              # Start ngrok tunnel for Twilio"
	@echo "  make black.run                                # Format code"

db.make_migrations:
	@poetry run alembic revision --autogenerate -m "$(m)"

db.up:
	@poetry run alembic upgrade head

db.down:
	@poetry run alembic downgrade base

db.reset:
	@echo "WARNING: this will DROP the entire 'public' schema and DELETE all data."
	@read -p "Type 'yes' to continue: " ans && [ "$$ans" = "yes" ] || (echo "Aborted." && exit 1)
	@echo "Dropping schema public..."
	@docker exec quiet_call_db psql -U app -d app_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo "Re-running migrations..."
	@poetry run alembic upgrade head
	@echo "Seeding templates + demo..."
	@poetry run python -m app.scripts.seed_templates
	@poetry run python -m app.scripts.seed_demo
	@echo "DB reset complete."

db.seed:
	@poetry run python -m app.scripts.seed_templates

db.seed.demo:
	@poetry run python -m app.scripts.seed_templates
	@poetry run python -m app.scripts.seed_demo


black.run:
	@poetry run black app

ruff.run:
	@poetry run ruff check app --fix && poetry run ruff format app

mypy.run:
	@poetry run mypy app

app.start:
	@echo "Building and starting all containers..."
	@docker compose up --build -d
	@echo "Quiet Call AI is running:"
	@echo "  API:      http://localhost:8000"
	@echo "  Docs:     http://localhost:8000/docs"
	@echo "  Postgres: localhost:5432"

app.stop:
	@echo "Stopping all containers..."
	@docker compose down
	@echo "All containers stopped."

app.logs:
	@docker compose logs -f

app.logs.api:
	@docker compose logs -f quiet_call_api

app.logs.worker:
	@docker compose logs -f quiet_call_worker

app.test:
	@echo "Running tests in Docker..."
	@docker compose --profile test up --build quiet_call_test --abort-on-container-exit --exit-code-from quiet_call_test

ngrok.start:
	@echo "Starting ngrok tunnel on port 8000..."
	@echo "Public URL: https://magda-pyramidal-everette.ngrok-free.dev"
	@echo "Press Ctrl+C to stop the tunnel."
	@ngrok http 8000 --domain=magda-pyramidal-everette.ngrok-free.dev