.PHONY: dev build lint test clean docker-up docker-down seed

dev:
	pnpm dev

build:
	pnpm build

lint:
	pnpm lint

test:
	pnpm test

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f

seed:
	python apps/api/scripts/seed.py

emulators:
	docker compose up firestore-emulator redis gcs-emulator

format:
	npx prettier --write "**/*.{js,ts,tsx,md,json}"

clean:
	rm -rf apps/web/.next apps/web/node_modules apps/api/__pycache__ .turbo
