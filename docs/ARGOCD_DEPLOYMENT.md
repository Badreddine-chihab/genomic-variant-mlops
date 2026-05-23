# Argo CD Deployment

This repository includes a Kubernetes base in `deploy/k8s/base` and an Argo CD
`Application` in `deploy/argocd/application.yaml`.

## Prerequisites

- A Kubernetes cluster with Argo CD installed.
- An ingress controller if you want to use `deploy/k8s/base/ingress.yaml`.
- Published container images for:
  - `genopredict-api`
  - `genopredict-frontend`
  - `genopredict-mlflow`
- A populated `processed-data` PVC containing:
  - `model_ready_dataset.parquet`
  - `final_training_dataset.parquet`

The default Kustomize images point at GitHub Container Registry:

```bash
ghcr.io/badreddine-chihab/genopredict-api:latest
ghcr.io/badreddine-chihab/genopredict-frontend:latest
ghcr.io/badreddine-chihab/genopredict-mlflow:latest
```

Update `deploy/k8s/base/kustomization.yaml` if your registry or tags differ.
The `Publish Container Images` GitHub Actions workflow publishes these images
on pushes to `main` and can also be run manually.

`deploy/argocd/application.yaml` includes Argo CD Image Updater annotations.
Install Argo CD Image Updater if you want new GHCR image tags to be written back
to `deploy/k8s/base/kustomization.yaml` automatically.

## Deploy

Apply the Argo CD application:

```bash
kubectl apply -f deploy/argocd/application.yaml
```

Or test the Kubernetes base directly:

```bash
kubectl apply -k deploy/k8s/base
```

If Argo CD reports `app path does not exist`, push this branch first or change
`targetRevision` in `deploy/argocd/application.yaml` to the branch that contains
`deploy/k8s/base`. Argo CD reads from Git, not from your local working tree.

If `kubectl` reports `connect: connection refused` against `127.0.0.1`, the
local kind cluster is stopped or kubeconfig is stale. Restart and refresh it:

```bash
docker start tp4-cluster-control-plane
kind export kubeconfig --name tp4-cluster
kubectl cluster-info
```

If Argo CD is not installed yet:

```bash
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply --server-side --force-conflicts -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server
```

## Access

With port forwarding:

```bash
kubectl -n genopredict port-forward svc/frontend 3000:3000
kubectl -n genopredict port-forward svc/api 8000:8000
kubectl -n genopredict port-forward svc/mlflow 5000:5000
kubectl -n genopredict port-forward svc/prometheus 9090:9090
kubectl -n genopredict port-forward svc/grafana 3001:3000
```

With ingress, point these hosts at your ingress controller and open:

- Frontend: `http://genopredict.local/`
- MLflow: `http://mlflow.genopredict.local/`
- Prometheus: `http://prometheus.genopredict.local/`
- Grafana: `http://grafana.genopredict.local/`

Change the default Grafana password in `deploy/k8s/base/secret-grafana.yaml`
before using this outside a local demo cluster.
