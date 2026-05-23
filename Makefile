PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: help diagrams test frontend-build k8s-render clean

help:
	@printf '%s\n' \
		'GenoPredict developer commands:' \
		'  make diagrams        Regenerate documentation SVGs' \
		'  make test            Run Python test suite' \
		'  make frontend-build  Build the React frontend' \
		'  make k8s-render      Render Kubernetes manifests' \
		'  make clean           Remove local Python/test caches'

diagrams:
	$(PYTHON) docs/generate_workflow_svgs.py

test:
	$(PYTHON) -m pytest -q

frontend-build:
	cd frontend && npm run build

k8s-render:
	kubectl kustomize deploy/k8s/base >/tmp/genopredict-k8s.yaml

clean:
	find . -path './.git' -prune -o -path './.venv' -prune -o \( -type d -name '__pycache__' -o -type d -name '.pytest_cache' -o -type d -name '.mypy_cache' -o -type d -name '.ruff_cache' \) -exec rm -rf {} +
