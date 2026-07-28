.PHONY: venv run migrate makemigrations seed superuser test up build-up down logs ps shell-postgres clean

# ─── Local dev (SQLite, no Docker required) ───────────────────────────────────

venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

run:
	python manage.py migrate --noinput
	python manage.py runserver 0.0.0.0:8080

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

seed:
	python manage.py seed_species

superuser:
	python manage.py createsuperuser

test:
	python manage.py test

# ─── Docker environment ───────────────────────────────────────────────────────

up:
	docker compose up -d

# Use when code or dependencies changed — rebuilds images first
build-up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f $(service)

ps:
	docker compose ps

shell-postgres:
	docker compose exec postgres psql -U omyfish -d omyfish

# ─── Utilities ────────────────────────────────────────────────────────────────

clean:
	docker compose down -v
