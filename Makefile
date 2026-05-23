PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: help docs diagrams feature-schema demo-check test frontend-build k8s-render k8s-render-dev k8s-render-prod clean

help:
	@printf '%s\n' \
		'GenoPredict developer commands:' \
		'  make docs            Regenerate docs artifacts' \
		'  make diagrams        Regenerate documentation SVGs' \
		'  make feature-schema  Regenerate feature schema docs' \
		'  make demo-check      Smoke check a running API service' \
		'  make test            Run Python test suite' \
		'  make frontend-build  Build the React frontend' \
		'  make k8s-render      Render base Kubernetes manifests' \
		'  make k8s-render-dev  Render dev overlay manifests' \
		'  make k8s-render-prod Render prod overlay manifests' \
		'  make clean           Remove local Python/test caches'

docs: diagrams feature-schema

diagrams:
	$(PYTHON) docs/generate_workflow_svgs.py

feature-schema:
	$(PYTHON) docs/generate_feature_schema_doc.py

demo-check:
	$(PYTHON) scripts/demo_check.py --retries 3

test:
	$(PYTHON) -m pytest -q

frontend-build:
	cd frontend && npm run build

k8s-render:
	kubectl kustomize deploy/k8s/base >/tmp/genopredict-k8s.yaml

k8s-render-dev:
	kubectl kustomize deploy/k8s/overlays/dev >/tmp/genopredict-k8s-dev.yaml

k8s-render-prod:
	kubectl kustomize deploy/k8s/overlays/prod >/tmp/genopredict-k8s-prod.yaml

clean:
	find . -path './.git' -prune -o -path './.venv' -prune -o \( -type d -name '__pycache__' -o -type d -name '.pytest_cache' -o -type d -name '.mypy_cache' -o -type d -name '.ruff_cache' \) -exec rm -rf {} +
