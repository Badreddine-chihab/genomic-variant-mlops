"""Generate clean architecture SVGs for the GenoPredict documentation."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap


ROOT = Path(__file__).resolve().parent


PALETTE = {
    "ink": "#172033",
    "muted": "#657083",
    "border": "#d8dee8",
    "surface": "#ffffff",
    "page": "#f5f7fb",
    "blue": "#2563eb",
    "teal": "#0f766e",
    "green": "#15803d",
    "amber": "#b45309",
    "red": "#b91c1c",
    "violet": "#6d28d9",
    "slate": "#475569",
}

SOFT = {
    "blue": "#eff6ff",
    "teal": "#f0fdfa",
    "green": "#f0fdf4",
    "amber": "#fffbeb",
    "red": "#fef2f2",
    "violet": "#f5f3ff",
    "slate": "#f8fafc",
}


@dataclass(frozen=True)
class Box:
    label: str
    title: str
    body: tuple[str, ...]
    tone: str = "blue"


def lines(text: str, width: int = 30) -> list[str]:
    return wrap(text, width=width, break_long_words=False)


def svg_open(title: str, subtitle: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'  <title id="title">{escape(title)}</title>',
        f'  <desc id="desc">{escape(subtitle)}</desc>',
        "  <defs>",
        "    <style>",
        "      .page { fill: #f5f7fb; }",
        "      .panel { fill: #ffffff; stroke: #d8dee8; stroke-width: 1.4; }",
        "      .title { font: 700 32px Arial, Helvetica, sans-serif; fill: #172033; }",
        "      .subtitle { font: 400 16px Arial, Helvetica, sans-serif; fill: #657083; }",
        "      .section { font: 700 15px Arial, Helvetica, sans-serif; fill: #172033; }",
        "      .label { font: 700 11px Arial, Helvetica, sans-serif; fill: #ffffff; letter-spacing: .7px; }",
        "      .box-title { font: 700 16px Arial, Helvetica, sans-serif; fill: #172033; }",
        "      .body { font: 400 13px Arial, Helvetica, sans-serif; fill: #465366; }",
        "      .caption { font: 600 12px Arial, Helvetica, sans-serif; fill: #657083; }",
        "      .mono { font: 600 12px Consolas, Menlo, monospace; fill: #465366; }",
        "      .arrow { stroke: #657083; stroke-width: 2.2; fill: none; marker-end: url(#arrow); }",
        "      .arrow-soft { stroke: #98a2b3; stroke-width: 2; fill: none; stroke-dasharray: 7 7; marker-end: url(#arrow-soft); }",
        "    </style>",
        '    <marker id="arrow" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto" markerUnits="strokeWidth">',
        '      <path d="M1 1 L9 5.5 L1 10 Z" fill="#657083"/>',
        "    </marker>",
        '    <marker id="arrow-soft" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto" markerUnits="strokeWidth">',
        '      <path d="M1 1 L9 5.5 L1 10 Z" fill="#98a2b3"/>',
        "    </marker>",
        "  </defs>",
        '  <rect class="page" width="100%" height="100%"/>',
        f'  <rect class="panel" x="32" y="28" width="{width - 64}" height="{height - 56}" rx="8"/>',
        f'  <text class="title" x="68" y="80">{escape(title)}</text>',
        f'  <text class="subtitle" x="68" y="108">{escape(subtitle)}</text>',
    ]


def svg_close(parts: list[str], name: str) -> None:
    path = ROOT / name
    path.write_text("\n".join(parts + ["</svg>", ""]), encoding="utf-8")
    print(path.relative_to(ROOT.parent))


def box(parts: list[str], x: int, y: int, w: int, h: int, item: Box) -> None:
    accent = PALETTE[item.tone]
    fill = SOFT[item.tone]
    parts.extend(
        [
            f'  <g>',
            f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="#d8dee8" stroke-width="1.4"/>',
            f'    <rect x="{x}" y="{y}" width="{w}" height="29" rx="8" fill="{accent}"/>',
            f'    <path d="M{x} {y + 21} H{x + w} V{y + 29} H{x} Z" fill="{accent}"/>',
            f'    <text class="label" x="{x + 16}" y="{y + 20}">{escape(item.label.upper())}</text>',
            f'    <text class="box-title" x="{x + 18}" y="{y + 58}">{escape(item.title)}</text>',
        ]
    )
    text_y = y + 84
    for line in item.body:
        for wrapped in lines(line):
            parts.append(f'    <text class="body" x="{x + 18}" y="{text_y}">{escape(wrapped)}</text>')
            text_y += 19
    parts.append("  </g>")


def arrow(parts: list[str], x1: int, y1: int, x2: int, y2: int, soft: bool = False) -> None:
    cls = "arrow-soft" if soft else "arrow"
    parts.append(f'  <path class="{cls}" d="M{x1} {y1} L{x2} {y2}"/>')


def elbow(parts: list[str], points: tuple[tuple[int, int], ...], soft: bool = False) -> None:
    cls = "arrow-soft" if soft else "arrow"
    start, *rest = points
    path = f"M{start[0]} {start[1]} " + " ".join(f"L{x} {y}" for x, y in rest)
    parts.append(f'  <path class="{cls}" d="{path}"/>')


def caption(parts: list[str], x: int, y: int, text: str, mono: bool = False) -> None:
    klass = "mono" if mono else "caption"
    parts.append(f'  <text class="{klass}" x="{x}" y="{y}">{escape(text)}</text>')


def flow_diagram(
    name: str,
    title: str,
    subtitle: str,
    items: tuple[Box, ...],
    caption_text: str,
    width: int = 1480,
    height: int = 560,
) -> None:
    parts = svg_open(title, subtitle, width, height)
    start_x, y, gap = 74, 205, 36
    box_w = (width - (start_x * 2) - gap * (len(items) - 1)) // len(items)
    box_h = 148
    centers = []
    for index, item in enumerate(items):
        x = start_x + index * (box_w + gap)
        box(parts, x, y, box_w, box_h, item)
        centers.append((x, y, x + box_w, y + box_h))
    for left, right in zip(centers, centers[1:]):
        arrow(parts, left[2], y + box_h // 2, right[0], y + box_h // 2)
    caption(parts, start_x, height - 70, caption_text, mono=True)
    svg_close(parts, name)


def project_diagram() -> None:
    width, height = 1800, 1480
    parts = svg_open(
        "GenoPredict MLOps Architecture",
        "A production-oriented map of data, model governance, serving, monitoring, security, and deployment.",
        width,
        height,
    )
    lanes = (
        ("Data and Feature Store", 150, ("DVC + S3", "Chromosome stitching", "Feature schema", "Parquet lookup")),
        ("Training and Governance", 395, ("Prefect flow", "XGBoost", "Evaluation + SHAP", "MLflow Production")),
        ("Application Workflows", 640, ("React UI", "Nginx proxy", "FastAPI", "VCF batch")),
        ("Monitoring and Operations", 885, ("Prediction logs", "Prometheus", "Drift monitor", "Grafana alerts")),
        ("Delivery", 1130, ("GitHub Actions", "GHCR images", "Argo CD", "AWS EC2 fallback")),
    )
    lane_colors = ("teal", "violet", "blue", "green", "amber")
    for (lane_title, y, labels), tone in zip(lanes, lane_colors):
        parts.append(f'  <rect x="68" y="{y}" width="1664" height="190" rx="8" fill="#ffffff" stroke="#d8dee8" stroke-width="1.4"/>')
        parts.append(f'  <text class="section" x="96" y="{y + 34}">{escape(lane_title)}</text>')
        lane_items = tuple(
            Box(str(index + 1), label, ("Primary project capability",), tone)
            for index, label in enumerate(labels)
        )
        x = 110
        for item in lane_items:
            box(parts, x, y + 58, 320, 92, item)
            x += 390
        for x1 in (430, 820, 1210):
            arrow(parts, x1, y + 104, x1 + 70, y + 104)

    elbow(parts, ((1490, 585), (1490, 640), (270, 640)), soft=True)
    elbow(parts, ((1490, 830), (1490, 885), (270, 885)), soft=True)
    elbow(parts, ((1490, 1075), (1490, 1130), (270, 1130)), soft=True)
    caption(parts, 86, height - 72, "Runtime ports: frontend 3000 | API 8000 | MLflow 5000 | Prometheus 9090 | Grafana 3001 | drift monitor 8001", mono=True)
    svg_close(parts, "project_workflow.svg")


def main() -> None:
    for old_svg in ROOT.glob("*.svg"):
        old_svg.unlink()

    flow_diagram(
        "data_pipeline.svg",
        "Data Pipeline",
        "Versioned genomic data becomes schema-safe parquet for training and serving.",
        (
            Box("source", "dbNSFP extracts", ("Raw chromosome files", "DVC pointers in repo"), "amber"),
            Box("version", "DVC + S3", ("Pull data when missing", "Remote artifact store"), "teal"),
            Box("stitch", "Stitching_chr.py", ("Polars/PyArrow processing", "Unified variant table"), "green"),
            Box("encode", "Feature encoding", ("Contracted model inputs", "Training-ready parquet"), "blue"),
            Box("serve", "Feature store", ("FastAPI local lookup", "S3 fallback bridge"), "violet"),
        ),
        "Command: python run_pipeline.py prepares data before training.",
    )
    flow_diagram(
        "training_pipeline.svg",
        "Training and Governance",
        "The pipeline trains, evaluates, explains, and promotes only eligible model runs.",
        (
            Box("flow", "Prefect launcher", ("run_pipeline.py", "YAML configuration"), "blue"),
            Box("train", "XGBoost", ("Training metrics", "MLflow artifacts"), "red"),
            Box("validate", "Evaluation", ("5-fold CV", "Quality evidence"), "slate"),
            Box("explain", "SHAP", ("Bar and summary plots", "Feature transparency"), "amber"),
            Box("promote", "Registry gate", ("Best finished run", "PR-AUC >= 0.80"), "violet"),
        ),
        "Output: models:/GenomicVariantModel@Production with tracked metrics and artifacts.",
    )
    flow_diagram(
        "inference_workflow.svg",
        "Online Inference",
        "The product UI calls FastAPI, which resolves features and returns calibrated prediction evidence.",
        (
            Box("ui", "React dashboard", ("Predict, VCF Lab", "Monitoring, Explainability"), "amber"),
            Box("proxy", "Nginx / Vite", ("Same-origin /api", "Local and Docker parity"), "slate"),
            Box("api", "FastAPI", ("Schema enforcement", "Model loaded at startup"), "blue"),
            Box("model", "MLflow model", ("Production alias", "Registry-backed loading"), "violet"),
            Box("result", "Prediction", ("Class, probability", "Confidence score"), "green"),
        ),
        "Endpoint family: /api/health, /api/predict, /api/model-info, /metrics.",
    )
    flow_diagram(
        "vcf_workflow.svg",
        "VCF Batch Workflow",
        "VCF records are normalized, enriched, predicted, summarized, and exported.",
        (
            Box("upload", "VCF upload", ("Header-safe parsing", "Record preview"), "amber"),
            Box("normalize", "ALT splitting", ("One row per allele", "Variant identifiers"), "teal"),
            Box("lookup", "Feature lookup", ("Parquet first", "S3 timeout guard"), "green"),
            Box("predict", "Batch predict", ("Found/not found/failed", "Max records guard"), "blue"),
            Box("export", "CSV report", ("Counters", "Reviewable results"), "violet"),
        ),
        "Endpoints: POST /api/upload-vcf and POST /api/vcf-batch-predict.",
    )
    flow_diagram(
        "monitoring_workflow.svg",
        "Monitoring and Drift",
        "Runtime events and metrics feed dashboards, alerts, and drift reports.",
        (
            Box("events", "Prediction log", ("JSONL event stream", "History endpoints"), "red"),
            Box("metrics", "API metrics", ("Latency and errors", "Model status"), "blue"),
            Box("drift", "Drift service", ("Continuous summary", "Report artifacts"), "green"),
            Box("scrape", "Prometheus", ("API + drift targets", "15s interval"), "amber"),
            Box("alert", "Grafana", ("Dashboards", "Provisioned alerts"), "violet"),
        ),
        "Alerts cover API availability, model loading, prediction errors, and data drift.",
    )
    flow_diagram(
        "cicd_security_workflow.svg",
        "CI/CD and Security",
        "GitHub Actions checks code quality, builds images, scans risk, and publishes deployable artifacts.",
        (
            Box("trigger", "Push / PR", ("main branch", "manual dispatch"), "slate"),
            Box("test", "Application CI", ("pytest", "frontend build"), "blue"),
            Box("image", "Compose build", ("config validation", "local image tags"), "green"),
            Box("scan", "DevSecOps", ("Bandit, audits", "Trivy SARIF"), "red"),
            Box("ship", "GHCR", ("latest + SHA tags", "Argo CD deploy input"), "violet"),
        ),
        "Workflow files live under .github/workflows.",
    )
    flow_diagram(
        "deployment_workflow.svg",
        "Deployment Workflow",
        "The project supports local Compose, GitOps Kubernetes, and a low-budget EC2 fallback.",
        (
            Box("local", "Docker Compose", ("Full app stack", "developer smoke tests"), "slate"),
            Box("registry", "GHCR images", ("API, frontend, MLflow", "SHA-tagged releases"), "blue"),
            Box("gitops", "Argo CD", ("Kustomize manifests", "self-healing sync"), "violet"),
            Box("monitor", "Observability", ("Prometheus", "Grafana"), "green"),
            Box("aws", "EC2 fallback", ("t3.small default", "cost guardrails"), "amber"),
        ),
        "Kubernetes manifests: deploy/k8s/base | Argo CD app: deploy/argocd/application.yaml.",
    )
    project_diagram()


if __name__ == "__main__":
    main()
