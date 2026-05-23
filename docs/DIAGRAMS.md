# Architecture Diagrams

This folder contains the generated SVG architecture set for GenoPredict. The
diagrams use one consistent visual system so they can be embedded in reports,
slides, or the README without looking like unrelated screenshots.

| Diagram | Purpose |
| --- | --- |
| [Full MLOps architecture](project_workflow.svg) | End-to-end map across data, model governance, serving, monitoring, and delivery. |
| [Data pipeline](data_pipeline.svg) | How versioned genomic data becomes schema-safe parquet for training and serving. |
| [Training and governance](training_pipeline.svg) | Training, evaluation, explainability, and MLflow promotion gates. |
| [Online inference](inference_workflow.svg) | Frontend, proxy, FastAPI, MLflow, and prediction response path. |
| [VCF batch workflow](vcf_workflow.svg) | Upload, ALT normalization, feature lookup, batch prediction, and export. |
| [Monitoring and drift](monitoring_workflow.svg) | Prediction logs, Prometheus, drift checks, Grafana dashboards, and alerts. |
| [CI/CD and security](cicd_security_workflow.svg) | Tests, image builds, security scans, GHCR publishing, and dependency upkeep. |
| [Deployment workflow](deployment_workflow.svg) | Local Compose, GitOps Kubernetes, observability, and EC2 fallback deployment. |

Regenerate the complete set with:

```bash
python docs/generate_workflow_svgs.py
```

The generator removes stale SVGs in this directory before writing the current
set, so committed diagrams stay aligned with the script.
