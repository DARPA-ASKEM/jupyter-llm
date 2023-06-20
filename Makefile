

.PHONY:build
build:
	docker build . -t jupyter-llm:latest

.PHONY:dev
dev:
	export `cat .env` && (cd dev_ui/ && npm run build) && poetry run python dev.py
