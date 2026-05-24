"""Generate polished icon-based architecture SVGs for GenoPredict docs."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap


ROOT = Path(__file__).resolve().parent


PALETTE = {
    "ink": "#172033",
    "muted": "#64748b",
    "border": "#d5dce8",
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
    "teal": "#ecfeff",
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
    icon: str = "box"


@dataclass(frozen=True)
class Zone:
    title: str
    x: int
    y: int
    w: int
    h: int
    tone: str = "slate"


def lines(text: str, width: int = 31) -> list[str]:
    return wrap(text, width=width, break_long_words=False)


def svg_open(title: str, subtitle: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'  <title id="title">{escape(title)}</title>',
        f'  <desc id="desc">{escape(subtitle)}</desc>',
        "  <defs>",
        "    <style>",
        "      .page { fill: #f5f7fb; }",
        "      .canvas { fill: #ffffff; stroke: #d5dce8; stroke-width: 1.3; }",
        "      .title { font: 700 34px Arial, Helvetica, sans-serif; fill: #172033; }",
        "      .subtitle { font: 400 16px Arial, Helvetica, sans-serif; fill: #64748b; }",
        "      .zone-title { font: 700 13px Arial, Helvetica, sans-serif; fill: #334155; letter-spacing: .5px; }",
        "      .label { font: 700 10px Arial, Helvetica, sans-serif; fill: #ffffff; letter-spacing: .7px; }",
        "      .box-title { font: 700 16px Arial, Helvetica, sans-serif; fill: #172033; }",
        "      .body { font: 400 13px Arial, Helvetica, sans-serif; fill: #475569; }",
        "      .caption { font: 600 12px Arial, Helvetica, sans-serif; fill: #64748b; }",
        "      .mono { font: 600 12px Consolas, Menlo, monospace; fill: #475569; }",
        "      .icon { fill: none; stroke: currentColor; stroke-width: 2.1; stroke-linecap: round; stroke-linejoin: round; }",
        "      .icon-fill { fill: currentColor; stroke: none; }",
        "      .arrow { stroke: #64748b; stroke-width: 2.3; fill: none; marker-end: url(#arrow); }",
        "      .arrow-soft { stroke: #94a3b8; stroke-width: 2; fill: none; stroke-dasharray: 7 7; marker-end: url(#arrow-soft); }",
        "    </style>",
        '    <marker id="arrow" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto" markerUnits="strokeWidth">',
        '      <path d="M1 1 L9 5.5 L1 10 Z" fill="#64748b"/>',
        "    </marker>",
        '    <marker id="arrow-soft" markerWidth="11" markerHeight="11" refX="9" refY="5.5" orient="auto" markerUnits="strokeWidth">',
        '      <path d="M1 1 L9 5.5 L1 10 Z" fill="#94a3b8"/>',
        "    </marker>",
        '    <filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">',
        '      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#0f172a" flood-opacity=".10"/>',
        "    </filter>",
        "  </defs>",
        '  <rect class="page" width="100%" height="100%"/>',
        f'  <rect class="canvas" x="28" y="26" width="{width - 56}" height="{height - 52}" rx="10"/>',
        f'  <text class="title" x="66" y="78">{escape(title)}</text>',
        f'  <text class="subtitle" x="66" y="108">{escape(subtitle)}</text>',
    ]


def svg_close(parts: list[str], name: str) -> None:
    path = ROOT / name
    path.write_text("\n".join(parts + ["</svg>", ""]), encoding="utf-8")
    print(path.relative_to(ROOT.parent))


def zone(parts: list[str], item: Zone) -> None:
    parts.extend(
        [
            f'  <rect x="{item.x}" y="{item.y}" width="{item.w}" height="{item.h}" rx="10" fill="{SOFT[item.tone]}" stroke="{PALETTE[item.tone]}" stroke-opacity=".22" stroke-width="1.2"/>',
            f'  <text class="zone-title" x="{item.x + 18}" y="{item.y + 28}">{escape(item.title.upper())}</text>',
        ]
    )


def icon_svg(name: str, x: int, y: int, color: str) -> str:
    common = f'transform="translate({x} {y})" style="color:{color}"'
    icons = {
        "database": '<ellipse class="icon" cx="12" cy="5" rx="8" ry="3"/><path class="icon" d="M4 5v10c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path class="icon" d="M4 10c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
        "cloud": '<path class="icon" d="M7 17h10a5 5 0 0 0 .4-10 7 7 0 0 0-13 2.5A4 4 0 0 0 7 17z"/>',
        "code": '<path class="icon" d="M8 7 3 12l5 5"/><path class="icon" d="m16 7 5 5-5 5"/><path class="icon" d="m14 4-4 16"/>',
        "train": '<path class="icon" d="M4 17h16"/><path class="icon" d="M7 17 5 21"/><path class="icon" d="m17 17 2 4"/><rect class="icon" x="5" y="4" width="14" height="11" rx="2"/><path class="icon" d="M8 8h8M8 12h5"/>',
        "chart": '<path class="icon" d="M4 19V5"/><path class="icon" d="M4 19h16"/><rect class="icon" x="7" y="12" width="2.5" height="5"/><rect class="icon" x="12" y="8" width="2.5" height="9"/><rect class="icon" x="17" y="5" width="2.5" height="12"/>',
        "brain": '<path class="icon" d="M9 5a4 4 0 0 0-4 4 4 4 0 0 0 1 7.8A4 4 0 0 0 12 20V5a3 3 0 0 0-3-3z"/><path class="icon" d="M15 5a4 4 0 0 1 4 4 4 4 0 0 1-1 7.8A4 4 0 0 1 12 20V5a3 3 0 0 1 3-3z"/>',
        "registry": '<path class="icon" d="M5 6h14v12H5z"/><path class="icon" d="M8 9h8M8 13h8"/><path class="icon" d="M8 18v3h8v-3"/>',
        "shield": '<path class="icon" d="M12 3 20 6v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path class="icon" d="m8.5 12 2.3 2.3L16 9"/>',
        "scan": '<path class="icon" d="M4 8V5a1 1 0 0 1 1-1h3"/><path class="icon" d="M16 4h3a1 1 0 0 1 1 1v3"/><path class="icon" d="M20 16v3a1 1 0 0 1-1 1h-3"/><path class="icon" d="M8 20H5a1 1 0 0 1-1-1v-3"/><path class="icon" d="M7 12h10"/>',
        "container": '<path class="icon" d="M3 8h18v10H3z"/><path class="icon" d="M6 8v10M10 8v10M14 8v10M18 8v10"/><path class="icon" d="M6 5h12v3H6z"/>',
        "server": '<rect class="icon" x="4" y="5" width="16" height="6" rx="1"/><rect class="icon" x="4" y="13" width="16" height="6" rx="1"/><path class="icon" d="M7 8h.1M7 16h.1"/>',
        "monitor": '<rect class="icon" x="4" y="5" width="16" height="11" rx="2"/><path class="icon" d="M9 20h6M12 16v4"/>',
        "api": '<path class="icon" d="M4 12h5"/><path class="icon" d="M15 12h5"/><circle class="icon" cx="12" cy="12" r="3"/><path class="icon" d="M12 4v5M12 15v5"/>',
        "file": '<path class="icon" d="M6 3h8l4 4v14H6z"/><path class="icon" d="M14 3v5h5"/><path class="icon" d="M9 13h6M9 17h6"/>',
        "grafana": '<circle class="icon" cx="12" cy="12" r="7"/><path class="icon" d="M12 12h5M12 12l-3-4M12 12l-4 4"/>',
        "alert": '<path class="icon" d="M12 3 22 20H2z"/><path class="icon" d="M12 9v5M12 17h.1"/>',
        "user": '<circle class="icon" cx="12" cy="8" r="4"/><path class="icon" d="M4 21a8 8 0 0 1 16 0"/>',
        "dna": '<path class="icon" d="M7 3c8 3 8 15 0 18"/><path class="icon" d="M17 3c-8 3-8 15 0 18"/><path class="icon" d="M8 7h8M8 12h8M8 17h8"/>',
        "box": '<path class="icon" d="M12 3 21 8l-9 5-9-5z"/><path class="icon" d="M3 8v8l9 5 9-5V8"/><path class="icon" d="M12 13v8"/>',
        "lock": '<rect class="icon" x="5" y="10" width="14" height="10" rx="2"/><path class="icon" d="M8 10V7a4 4 0 0 1 8 0v3"/>',
        "rocket": '<path class="icon" d="M12 15 9 12c1-5 4-8 10-9-1 6-4 9-9 10z"/><path class="icon" d="M9 12 5 13l3 3 1-4z"/><path class="icon" d="M12 15l-1 4 3-3-2-1z"/>',
        "git": '<circle class="icon" cx="6" cy="6" r="2"/><circle class="icon" cx="18" cy="18" r="2"/><circle class="icon" cx="18" cy="6" r="2"/><path class="icon" d="M8 6h8M8 7l8 9"/>',
    }
    body = icons.get(name, icons["box"])
    return f'    <g {common}>{body}</g>'


def box(parts: list[str], x: int, y: int, w: int, h: int, item: Box) -> None:
    accent = PALETTE[item.tone]
    fill = SOFT[item.tone]
    parts.extend(
        [
            '  <g filter="url(#shadow)">',
            f'    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="#d5dce8" stroke-width="1.3"/>',
            f'    <rect x="{x}" y="{y}" width="{w}" height="6" rx="3" fill="{accent}"/>',
            f'    <rect x="{x + 18}" y="{y + 24}" width="42" height="42" rx="10" fill="{fill}" stroke="{accent}" stroke-opacity=".28"/>',
            icon_svg(item.icon, x + 27, y + 33, accent),
            f'    <rect x="{x + 72}" y="{y + 26}" width="{min(92, max(58, len(item.label) * 6 + 18))}" height="22" rx="11" fill="{accent}"/>',
            f'    <text class="label" x="{x + 86}" y="{y + 41}">{escape(item.label.upper())}</text>',
            f'    <text class="box-title" x="{x + 72}" y="{y + 66}">{escape(item.title)}</text>',
        ]
    )
    text_y = y + 94
    for line in item.body:
        for wrapped in lines(line):
            parts.append(f'    <text class="body" x="{x + 22}" y="{text_y}">{escape(wrapped)}</text>')
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
    zones: tuple[Zone, ...],
    items: tuple[Box, ...],
    caption_text: str,
    width: int = 1500,
    height: int = 620,
) -> None:
    parts = svg_open(title, subtitle, width, height)
    for item in zones:
        zone(parts, item)
    start_x, y, gap = 74, 230, 34
    box_w = (width - (start_x * 2) - gap * (len(items) - 1)) // len(items)
    box_h = 170
    centers = []
    for index, item in enumerate(items):
        x = start_x + index * (box_w + gap)
        box(parts, x, y, box_w, box_h, item)
        centers.append((x, y, x + box_w, y + box_h))
    for left, right in zip(centers, centers[1:]):
        arrow(parts, left[2], y + box_h // 2, right[0], y + box_h // 2)
    caption(parts, start_x, height - 72, caption_text, mono=True)
    svg_close(parts, name)


def project_diagram() -> None:
    width, height = 1840, 1520
    parts = svg_open(
        "GenoPredict MLOps Architecture",
        "Production-oriented lifecycle view with data, governance, serving, monitoring, security, and deployment.",
        width,
        height,
    )
    lanes = (
        ("Data and Feature Store", 150, ("DVC + S3", "Chromosome stitching", "Feature schema doc", "Parquet lookup"), ("cloud", "code", "file", "database"), "teal"),
        ("Training and Governance", 405, ("Prefect flow", "XGBoost", "Model card", "MLflow Production"), ("train", "brain", "file", "registry"), "violet"),
        ("Application Workflows", 660, ("React UI", "Nginx proxy", "FastAPI", "VCF batch"), ("monitor", "server", "api", "dna"), "blue"),
        ("Monitoring and Operations", 915, ("Demo check", "Prometheus", "Drift monitor", "Grafana alerts"), ("scan", "chart", "alert", "grafana"), "green"),
        ("Delivery and Security", 1170, ("GitHub Actions", "GHCR images", "K8s overlays", "AWS EC2 fallback"), ("git", "container", "rocket", "cloud"), "amber"),
    )
    for lane_title, y, labels, icons, tone in lanes:
        zone(parts, Zone(lane_title, 68, y, 1704, 205, tone))
        x = 110
        for index, (label, icon_name) in enumerate(zip(labels, icons), start=1):
            box(parts, x, y + 58, 330, 112, Box(str(index), label, ("Documented project capability",), tone, icon_name))
            x += 400
        for x1 in (440, 840, 1240):
            arrow(parts, x1, y + 114, x1 + 70, y + 114)

    elbow(parts, ((1510, 575), (1510, 660), (280, 660)), soft=True)
    elbow(parts, ((1510, 830), (1510, 915), (280, 915)), soft=True)
    elbow(parts, ((1510, 1085), (1510, 1170), (280, 1170)), soft=True)
    caption(parts, 86, height - 74, "Ops commands: make docs | make demo-check | make k8s-render-dev | make k8s-render-prod", mono=True)
    svg_close(parts, "project_workflow.svg")


def main() -> None:
    for old_svg in ROOT.glob("*.svg"):
        old_svg.unlink()

    flow_diagram(
        "data_pipeline.svg",
        "Data Pipeline",
        "Versioned genomic data becomes schema-safe parquet for training and serving.",
        (Zone("Data Layer", 56, 152, 430, 300, "teal"), Zone("Processing", 516, 152, 560, 300, "green"), Zone("Serving Data", 1106, 152, 338, 300, "violet")),
        (
            Box("source", "dbNSFP extracts", ("Raw chromosome files", "DVC pointers in repo"), "amber", "dna"),
            Box("version", "DVC + S3", ("Pull data when missing", "Remote artifact store"), "teal", "cloud"),
            Box("stitch", "Stitching_chr.py", ("Polars/PyArrow processing", "Unified variant table"), "green", "code"),
            Box("encode", "Feature encoding", ("Contracted model inputs", "Generated schema docs"), "blue", "file"),
            Box("serve", "Feature store", ("FastAPI local lookup", "S3 fallback bridge"), "violet", "database"),
        ),
        "Commands: python run_pipeline.py | make feature-schema.",
    )
    flow_diagram(
        "training_pipeline.svg",
        "Training and Governance",
        "The pipeline trains, evaluates, explains, and promotes only eligible model runs.",
        (Zone("Experimentation", 56, 152, 645, 300, "blue"), Zone("Governance", 731, 152, 713, 300, "violet")),
        (
            Box("flow", "Prefect launcher", ("run_pipeline.py", "YAML configuration"), "blue", "train"),
            Box("train", "XGBoost", ("Training metrics", "MLflow artifacts"), "red", "brain"),
            Box("validate", "Evaluation", ("5-fold CV", "Quality evidence"), "slate", "chart"),
            Box("explain", "Model card + SHAP", ("Documented limits", "Feature transparency"), "amber", "file"),
            Box("promote", "Registry gate", ("Best finished run", "PR-AUC >= 0.80"), "violet", "registry"),
        ),
        "Outputs: models:/GenomicVariantModel@Production, docs/MODEL_CARD.md, and SHAP artifacts.",
    )
    flow_diagram(
        "inference_workflow.svg",
        "Online Inference",
        "The product UI calls FastAPI, which resolves features and returns calibrated prediction evidence.",
        (Zone("Public Entry", 56, 152, 430, 300, "amber"), Zone("Application Runtime", 516, 152, 560, 300, "blue"), Zone("ML Runtime", 1106, 152, 338, 300, "green")),
        (
            Box("ui", "React dashboard", ("Predict, VCF Lab", "Monitoring, Explainability"), "amber", "monitor"),
            Box("proxy", "Nginx / Vite", ("Same-origin /api", "Local and Docker parity"), "slate", "server"),
            Box("api", "FastAPI", ("Schema enforcement", "Model loaded at startup"), "blue", "api"),
            Box("model", "MLflow model", ("Production alias", "Registry-backed loading"), "violet", "registry"),
            Box("result", "Prediction", ("Class, probability", "Confidence score"), "green", "chart"),
        ),
        "Endpoint family: /api/health, /api/predict, /api/model-info, /metrics.",
    )
    flow_diagram(
        "vcf_workflow.svg",
        "VCF Batch Workflow",
        "VCF records are normalized, enriched, predicted, summarized, and exported.",
        (Zone("Input", 56, 152, 430, 300, "amber"), Zone("Batch Processing", 516, 152, 560, 300, "teal"), Zone("Review Output", 1106, 152, 338, 300, "violet")),
        (
            Box("upload", "VCF upload", ("Header-safe parsing", "Record preview"), "amber", "file"),
            Box("normalize", "ALT splitting", ("One row per allele", "Variant identifiers"), "teal", "dna"),
            Box("lookup", "Feature lookup", ("Parquet first", "S3 timeout guard"), "green", "database"),
            Box("predict", "Batch predict", ("Found/not found/failed", "Max records guard"), "blue", "api"),
            Box("export", "CSV report", ("Counters", "Reviewable results"), "violet", "chart"),
        ),
        "Endpoints: POST /api/upload-vcf and POST /api/vcf-batch-predict.",
    )
    flow_diagram(
        "monitoring_workflow.svg",
        "Monitoring and Drift",
        "Runtime events and metrics feed dashboards, alerts, and drift reports.",
        (Zone("Runtime Signals", 56, 152, 430, 300, "red"), Zone("Observability", 516, 152, 560, 300, "green"), Zone("Action", 1106, 152, 338, 300, "violet")),
        (
            Box("events", "Prediction log", ("JSONL event stream", "History endpoints"), "red", "file"),
            Box("demo", "Demo check", ("Health, model info", "metrics and drift"), "blue", "scan"),
            Box("drift", "Drift service", ("Continuous summary", "Report artifacts"), "green", "alert"),
            Box("scrape", "Prometheus", ("API + drift targets", "15s interval"), "amber", "chart"),
            Box("alert", "Grafana", ("Dashboards", "Provisioned alerts"), "violet", "grafana"),
        ),
        "Commands: make demo-check | make test.",
    )
    flow_diagram(
        "cicd_security_workflow.svg",
        "CI/CD and Security",
        "GitHub Actions checks code quality, builds images, scans risk, and publishes deployable artifacts.",
        (Zone("Source Control", 56, 152, 430, 300, "slate"), Zone("Quality and Security", 516, 152, 560, 300, "red"), Zone("Release", 1106, 152, 338, 300, "violet")),
        (
            Box("trigger", "Push / PR", ("main branch", "manual dispatch"), "slate", "git"),
            Box("test", "Application CI", ("pytest", "frontend build"), "blue", "code"),
            Box("image", "Compose build", ("config validation", "local image tags"), "green", "container"),
            Box("scan", "DevSecOps", ("Bandit, audits", "Trivy SARIF"), "red", "shield"),
            Box("ship", "GHCR", ("latest + SHA tags", "Argo CD deploy input"), "violet", "rocket"),
        ),
        "Workflow files live under .github/workflows.",
    )
    flow_diagram(
        "deployment_workflow.svg",
        "Deployment Workflow",
        "The project supports local Compose, GitOps Kubernetes, and a low-budget EC2 fallback.",
        (Zone("Local", 56, 152, 300, 300, "slate"), Zone("GitOps", 386, 152, 690, 300, "violet"), Zone("Cloud Fallback", 1106, 152, 338, 300, "amber")),
        (
            Box("local", "Docker Compose", ("Full app stack", "developer smoke tests"), "slate", "container"),
            Box("registry", "GHCR images", ("API, frontend, MLflow", "SHA-tagged releases"), "blue", "box"),
            Box("gitops", "Argo CD", ("dev/prod overlays", "self-healing sync"), "violet", "rocket"),
            Box("monitor", "Observability", ("Prometheus", "Grafana"), "green", "grafana"),
            Box("aws", "EC2 fallback", ("t3.small default", "cost guardrails"), "amber", "cloud"),
        ),
        "Kubernetes manifests: deploy/k8s/base and deploy/k8s/overlays/{dev,prod}.",
    )
    project_diagram()


if __name__ == "__main__":
    main()
