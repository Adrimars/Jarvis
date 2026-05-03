start:
	docker compose up -d

stop:
	docker compose down

restart:
	docker compose restart

build:
	docker compose build --no-cache

logs:
	docker compose logs -f $(s)

health:
	docker compose ps

update:
	git pull
	docker compose build
	docker compose up -d

backup:
	docker compose exec agent-core python -c "from core.learning import LearningEngine; from core.profile import load_profile; LearningEngine()._backup(load_profile()); print('Backup done.')"
