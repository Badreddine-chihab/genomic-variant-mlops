#!/bin/bash
set -e

# Start MLflow in the background
mlflow server \
    --backend-store-uri sqlite:////mlflow/mlflow.db \
    --serve-artifacts \
    --artifacts-destination /mlflow/mlruns \
    --default-artifact-root mlflow-artifacts:/ \
    --host 0.0.0.0 \
    --port 5000 \
    --allowed-hosts "localhost,localhost:5000,127.0.0.1,127.0.0.1:5000,mlflow,mlflow:5000,genopredict-mlflow,genopredict-mlflow:5000" \
    --workers 2 &

MLFLOW_PID=$!

# Give MLflow a moment to start
sleep 2

# Register the model
python /register_model.py
touch /tmp/mlflow-ready

# Wait for MLflow to finish
wait $MLFLOW_PID
