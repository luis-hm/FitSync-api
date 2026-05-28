PORT ?= 8000

.PHONY: db migrate run dev check stop

db:
	docker compose up --wait -d postgres

migrate:
	poetry run python manage.py migrate

run:
	poetry run daphne -b 0.0.0.0 -p $(PORT) config.asgi:application

dev: db migrate run

check:
	poetry run python manage.py check

stop:
	docker compose stop postgres
