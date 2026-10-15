.PHONY: venv run migrate makemigrations seed superuser test up build-up check-frontend-pin down logs ps shell-postgres clean

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
	@$(MAKE) --no-print-directory check-frontend-pin
	docker compose up -d

# Use when code or dependencies changed — rebuilds images first
build-up:
	@$(MAKE) --no-print-directory check-frontend-pin
	docker compose up -d --build

# Warns (doesn't block) if docker-compose.yml's pinned frontend image tag is behind
# a locally-cloned ../omyfish-frontend checkout — the gotcha where a frontend feature
# lands but nothing shows up until the pin is bumped.
check-frontend-pin:
	@FRONTEND_PIN=$$(grep -oE 'omyfish-frontend:[a-f0-9]+' docker-compose.yml | head -1 | cut -d: -f2); \
	if [ -d ../omyfish-frontend/.git ]; then \
		FRONTEND_HEAD=$$(git -C ../omyfish-frontend rev-parse --short HEAD 2>/dev/null); \
		if [ -n "$$FRONTEND_HEAD" ] && [ -n "$$FRONTEND_PIN" ] && [ "$$FRONTEND_PIN" != "$$FRONTEND_HEAD" ]; then \
			echo "warning: docker-compose.yml pins frontend image tag $$FRONTEND_PIN, but ../omyfish-frontend is at $$FRONTEND_HEAD — bump the pin (see README) to pick up frontend changes"; \
		fi; \
	fi

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
