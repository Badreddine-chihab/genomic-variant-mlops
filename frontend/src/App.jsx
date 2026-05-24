import { useEffect, useMemo, useState } from "react";
import {
  fetchFeatures,
  getHealth,
  getModelInfo,
  getMonitoringDrift,
  getMonitoringPredictions,
  getMonitoringSummary,
  predictVariant,
  predictVcfBatch,
  uploadVcf
} from "./api";

const CHROMS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "X", "Y", "M"];
const STORAGE_KEY = "genopredict_prediction_history_v2";
const AUTH_KEY = "genopredict_demo_auth";
const REVIEW_STATUSES = ["Needs review", "Reviewed", "Flagged", "Exported"];
const DEMO_BATCH_RECORDS = [
  { chrom: "11", pos: "209271", ref: "C", alt: "A" },
  { chrom: "11", pos: "298524", ref: "A", alt: "C" },
  { chrom: "11", pos: "299372", ref: "G", alt: "A" },
  { chrom: "11", pos: "299372", ref: "G", alt: "C" },
  { chrom: "11", pos: "299391", ref: "G", alt: "A" },
  { chrom: "11", pos: "533467", ref: "C", alt: "G" },
  { chrom: "7", pos: "140453136", ref: "A", alt: "T" }
];

const INITIAL_FORM = {
  chrom: "11",
  pos: "209271",
  ref: "C",
  alt: "A",
  sift: "",
  polyphen: "",
  cadd: "",
  alt_freq: ""
};

const ICONS = {
  dashboard: "M4 13h7V4H4v9Zm9 7h7V4h-7v16ZM4 20h7v-5H4v5Z",
  search: "m21 21-4.35-4.35M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z",
  upload: "M12 3v12m0-12 4 4m-4-4-4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  brain: "M9 4a4 4 0 0 0-4 4 4 4 0 0 0 1 7.7A4 4 0 0 0 12 20V4a3 3 0 0 0-3-3Zm6 0a4 4 0 0 1 4 4 4 4 0 0 1-1 7.7A4 4 0 0 1 12 20V4a3 3 0 0 1 3-3Z",
  shield: "M12 3 20 6v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6l8-3Z",
  file: "M6 3h8l4 4v14H6V3Zm8 0v5h5",
  logOut: "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3",
  play: "M7 4v16l13-8L7 4Z",
  refresh: "M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6",
  download: "M12 3v12m0 0 4-4m-4 4-4-4M4 19h16",
  print: "M7 8V3h10v5M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7v-7Z",
  alert: "M12 3 22 20H2L12 3Zm0 6v5m0 3h.01",
  check: "M20 6 9 17l-5-5",
  lock: "M6 10V7a6 6 0 0 1 12 0v3M5 10h14v11H5V10Z",
  database: "M4 6c0-2 16-2 16 0v12c0 2-16 2-16 0V6Zm0 6c0 2 16 2 16 0M4 6c0 2 16 2 16 0",
  dna: "M7 3c8 4 8 14 0 18M17 3c-8 4-8 14 0 18M8 7h8M8 12h8M8 17h8",
  settings: "M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm8.5 4a7.8 7.8 0 0 0-.12-1.35l2.02-1.58-2-3.46-2.38.96a8 8 0 0 0-2.34-1.35L15.34 2h-4l-.34 3.22a8 8 0 0 0-2.34 1.35l-2.38-.96-2 3.46 2.02 1.58A8.4 8.4 0 0 0 6.18 12c0 .46.04.91.12 1.35l-2.02 1.58 2 3.46 2.38-.96a8 8 0 0 0 2.34 1.35l.34 3.22h4l.34-3.22a8 8 0 0 0 2.34-1.35l2.38.96 2-3.46-2.02-1.58c.08-.44.12-.89.12-1.35Z"
};

function Icon({ name, size = 20 }) {
  return (
    <svg className="ui-icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d={ICONS[name] || ICONS.dashboard} />
    </svg>
  );
}

function toNumber(value) {
  if (value === undefined || value === null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function labelFromPrediction(prediction) {
  return Number(prediction) === 1 ? "PATHOGENIC" : "BENIGN";
}

function pct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

function fmt(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toFixed(digits);
}

function escapeHtml(value) {
  return String(value ?? "N/A").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));
}

function extractNumeric(row, candidates, fallback = "") {
  for (const key of candidates) {
    if (row[key] !== undefined && row[key] !== null && row[key] !== "") return String(row[key]);
  }
  return fallback;
}

function normalizeFetchedRow(row, currentForm) {
  return {
    chrom: String(row["#chr"] ?? row.CHROM ?? currentForm.chrom),
    pos: String(row["pos(1-based)"] ?? row.POS ?? currentForm.pos),
    ref: String(row.ref ?? row.REF ?? currentForm.ref).toUpperCase(),
    alt: String(row.alt ?? row.ALT ?? currentForm.alt).toUpperCase(),
    sift: extractNumeric(row, ["SIFT_score", "SIFT"], currentForm.sift),
    polyphen: extractNumeric(row, ["Polyphen2_HVAR_score", "Polyphen2_HDIV_score", "PolyPhen"], currentForm.polyphen),
    cadd: extractNumeric(row, ["CADD_phred", "CADD"], currentForm.cadd),
    alt_freq: extractNumeric(row, ["gnomAD_exomes_AF", "ALT_FREQ"], currentForm.alt_freq)
  };
}

function buildPredictionPayload(form) {
  const payload = {
    chrom: form.chrom,
    pos: String(form.pos).trim(),
    ref: String(form.ref).trim().toUpperCase(),
    alt: String(form.alt).trim().toUpperCase()
  };
  for (const key of ["sift", "polyphen", "cadd", "alt_freq"]) {
    const value = toNumber(form[key]);
    if (value !== null) payload[key] = value;
  }
  return payload;
}

function isManualSpecsComplete(form) {
  return ["sift", "polyphen", "cadd", "alt_freq"].every((key) => toNumber(form[key]) !== null);
}

function variantLabel(row) {
  return `${row.chrom}:${row.pos} ${row.ref}>${row.alt}`;
}

function confidenceBand(confidence) {
  if (confidence === null || confidence === undefined) return "Unknown";
  if (confidence >= 0.85) return "High";
  if (confidence >= 0.6) return "Moderate";
  return "Low";
}

function triageLabel(row) {
  if (!row) return "Pending";
  if (row.confidence < 0.6) return "Insufficient evidence";
  if (row.label === "PATHOGENIC" && (row.probability ?? 0) >= 0.75) return "High priority";
  if (row.label === "PATHOGENIC") return "Review priority";
  return "Low priority";
}

function getFeatureDrivers(features = {}) {
  const rows = [];
  const cadd = toNumber(features.cadd);
  const altFreq = toNumber(features.alt_freq);
  const sift = toNumber(features.sift);
  const polyphen = toNumber(features.polyphen);

  if (cadd !== null) {
    rows.push({
      name: "CADD",
      value: cadd.toFixed(3),
      direction: cadd >= 20 ? "Raises concern" : cadd >= 10 ? "Moderate signal" : "Lower signal",
      strength: Math.min(100, Math.max(8, (cadd / 35) * 100))
    });
  }
  if (altFreq !== null) {
    rows.push({
      name: "ALT frequency",
      value: altFreq.toExponential(2),
      direction: altFreq < 0.001 ? "Rare variant" : altFreq < 0.01 ? "Uncommon" : "Commoner allele",
      strength: Math.min(100, Math.max(8, (1 - Math.min(altFreq, 0.02) / 0.02) * 100))
    });
  }
  if (sift !== null) {
    rows.push({
      name: "SIFT",
      value: sift.toFixed(3),
      direction: sift <= 0.05 ? "Damaging signal" : "Tolerated signal",
      strength: Math.min(100, Math.max(8, (1 - sift) * 100))
    });
  }
  if (polyphen !== null) {
    rows.push({
      name: "PolyPhen",
      value: polyphen.toFixed(3),
      direction: polyphen >= 0.85 ? "Probably damaging" : polyphen >= 0.45 ? "Possibly damaging" : "Benign leaning",
      strength: Math.min(100, Math.max(8, polyphen * 100))
    });
  }
  return rows.sort((a, b) => b.strength - a.strength).slice(0, 4);
}

function exportReviewReport(row, modelInfo) {
  if (!row) return;
  const features = row.features || {};
  const lines = [
    "GenoPredict Variant Evidence Report",
    "",
    `Generated: ${new Date().toLocaleString()}`,
    `Variant: ${row.variant}`,
    `Prediction: ${row.label}`,
    `Triage: ${triageLabel(row)}`,
    `Probability: ${pct(row.probability, 3)}`,
    `Confidence: ${pct(row.confidence, 3)}`,
    `Review status: ${row.reviewStatus || "Needs review"}`,
    `Source: ${row.source}`,
    "",
    "Model provenance",
    `Model: ${modelInfo?.model_name || row.modelName || "unknown"}`,
    `Registry URI: ${modelInfo?.model_uri || row.modelUri || "unknown"}`,
    `Model status: ${modelInfo?.model_status || "unknown"}`,
    "",
    "Feature values",
    `SIFT: ${features.sift ?? "N/A"}`,
    `PolyPhen: ${features.polyphen ?? "N/A"}`,
    `CADD: ${features.cadd ?? "N/A"}`,
    `ALT_FREQ: ${features.alt_freq ?? "N/A"}`,
    "",
    "Evidence drivers",
    ...getFeatureDrivers(features).map((driver) => `- ${driver.name}: ${driver.value} (${driver.direction})`),
    "",
    "Clinical note",
    "This output is decision support only and should be reviewed by qualified laboratory staff."
  ];

  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `genopredict_evidence_${row.variant.replace(/[^a-z0-9]+/gi, "_")}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

function printReviewReport(row, modelInfo) {
  if (!row) return;
  const features = row.features || {};
  const drivers = getFeatureDrivers(features);
  const reportWindow = window.open("", "_blank", "noopener,noreferrer");
  if (!reportWindow) return;
  reportWindow.document.write(`
    <html>
      <head>
        <title>GenoPredict Evidence Report</title>
        <style>
          body { font-family: Arial, sans-serif; color: #172033; margin: 32px; }
          h1 { font-size: 24px; margin-bottom: 4px; }
          h2 { font-size: 15px; margin-top: 24px; border-bottom: 1px solid #d8dee9; padding-bottom: 6px; }
          table { border-collapse: collapse; width: 100%; margin-top: 8px; }
          td, th { border: 1px solid #d8dee9; padding: 8px; text-align: left; font-size: 13px; }
          .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; background: #eef4ff; }
          .note { color: #5f6b7a; font-size: 12px; margin-top: 24px; }
        </style>
      </head>
      <body>
        <h1>GenoPredict Variant Evidence Report</h1>
        <div class="badge">${escapeHtml(row.reviewStatus || "Needs review")}</div>
        <h2>Variant Summary</h2>
        <table>
          <tr><th>Variant</th><td>${escapeHtml(row.variant)}</td></tr>
          <tr><th>Prediction</th><td>${escapeHtml(row.label)}</td></tr>
          <tr><th>Triage</th><td>${escapeHtml(triageLabel(row))}</td></tr>
          <tr><th>Probability</th><td>${pct(row.probability, 3)}</td></tr>
          <tr><th>Confidence</th><td>${pct(row.confidence, 3)} (${confidenceBand(row.confidence)})</td></tr>
          <tr><th>Source</th><td>${escapeHtml(row.source)}</td></tr>
          <tr><th>Timestamp</th><td>${escapeHtml(row.timestamp)}</td></tr>
        </table>
        <h2>Feature Values</h2>
        <table>
          <tr><th>SIFT</th><td>${escapeHtml(features.sift)}</td></tr>
          <tr><th>PolyPhen</th><td>${escapeHtml(features.polyphen)}</td></tr>
          <tr><th>CADD</th><td>${escapeHtml(features.cadd)}</td></tr>
          <tr><th>ALT_FREQ</th><td>${escapeHtml(features.alt_freq)}</td></tr>
        </table>
        <h2>Model Provenance</h2>
        <table>
          <tr><th>Model</th><td>${escapeHtml(modelInfo?.model_name || row.modelName || "unknown")}</td></tr>
          <tr><th>Status</th><td>${escapeHtml(modelInfo?.model_status || "unknown")}</td></tr>
          <tr><th>Registry URI</th><td>${escapeHtml(modelInfo?.model_uri || row.modelUri || "unknown")}</td></tr>
        </table>
        <h2>Evidence Drivers</h2>
        <table>
          <tr><th>Feature</th><th>Value</th><th>Direction</th></tr>
          ${drivers.map((driver) => `<tr><td>${escapeHtml(driver.name)}</td><td>${escapeHtml(driver.value)}</td><td>${escapeHtml(driver.direction)}</td></tr>`).join("")}
        </table>
        <p class="note">This output is decision support only and should be reviewed by qualified laboratory staff.</p>
      </body>
    </html>
  `);
  reportWindow.document.close();
  reportWindow.focus();
  reportWindow.print();
}

function exportHistoryCSV(history) {
  if (!history.length) return;
  const headers = ["timestamp", "variant", "source", "review_status", "prediction", "triage", "probability_percent", "confidence_percent"];
  const lines = [headers.join(",")];
  for (const row of history) {
    const cells = [
      row.timestamp,
      row.variant,
      row.source,
      row.reviewStatus || "Needs review",
      row.label,
      triageLabel(row),
      row.probability === null || row.probability === undefined ? "" : (row.probability * 100).toFixed(3),
      row.confidence === null || row.confidence === undefined ? "" : (row.confidence * 100).toFixed(3)
    ];
    lines.push(cells.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","));
  }

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "genopredict_review_queue.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function exportBatchReportCSV(summary, rows) {
  if (!rows.length) return;
  const headers = ["chrom", "pos", "ref", "alt", "status", "prediction", "label", "triage", "probability_percent", "confidence_percent", "message", "processed", "predicted", "not_found", "failed"];
  const lines = [headers.join(",")];
  for (const row of rows) {
    const values = [
      row.chrom,
      row.pos,
      row.ref,
      row.alt,
      row.status,
      row.prediction ?? "",
      row.label ?? "",
      row.label ? triageLabel({ label: row.label, probability: row.probability, confidence: row.confidence_score }) : "",
      row.probability !== null && row.probability !== undefined ? (row.probability * 100).toFixed(3) : "",
      row.confidence_score !== null && row.confidence_score !== undefined ? (row.confidence_score * 100).toFixed(3) : "",
      row.message ?? "",
      summary?.processed ?? "",
      summary?.predicted ?? "",
      summary?.notFound ?? "",
      summary?.failed ?? ""
    ];
    lines.push(values.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "genopredict_vcf_batch_report.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function StatusPill({ tone = "neutral", children }) {
  return <span className={`status-pill status-${tone}`}>{children}</span>;
}

function StatCard({ icon, label, value, subtext, tone = "blue" }) {
  return (
    <section className="metric-card">
      <div className={`metric-icon tone-${tone}`}><Icon name={icon} /></div>
      <div>
        <p className="metric-label">{label}</p>
        <h3>{value}</h3>
        {subtext && <p className="metric-subtext">{subtext}</p>}
      </div>
    </section>
  );
}

function EmptyState({ icon = "file", title, text }) {
  return (
    <div className="empty-state">
      <Icon name={icon} size={30} />
      <h5>{title}</h5>
      <p>{text}</p>
    </div>
  );
}

function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState("");

  const submit = (event) => {
    event.preventDefault();
    if (username === "admin" && password === "admin") {
      sessionStorage.setItem(AUTH_KEY, "true");
      onLogin();
      return;
    }
    setError("Invalid demo credentials.");
  };

  return (
    <main className="login-screen">
      <section className="login-visual">
        <div className="brand-mark"><Icon name="dna" size={34} /></div>
        <h1>GenoPredict</h1>
        <p>Clinical variant prioritization workspace for model evidence, batch VCF review, and runtime monitoring.</p>
        <div className="login-proof">
          <span><Icon name="shield" /> Demo access</span>
          <span><Icon name="brain" /> XGBoost evidence model</span>
          <span><Icon name="activity" /> Drift-aware operations</span>
        </div>
      </section>
      <form className="login-panel" onSubmit={submit}>
        <div className="login-lock"><Icon name="lock" size={28} /></div>
        <h2>Sign in</h2>
        <p>Use the demo account to open the lab console.</p>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn-primary-modern" type="submit">
          <Icon name="play" /> Enter workspace
        </button>
        <p className="demo-note">Demo credentials: admin / admin</p>
      </form>
    </main>
  );
}

function AppShell({ page, setPage, health, modelInfo, history, onLogout, children, onExportHistory, onClearHistory }) {
  const navItems = [
    ["overview", "dashboard", "Dashboard"],
    ["predict", "search", "Variant"],
    ["vcf", "upload", "VCF Lab"],
    ["monitoring", "activity", "Monitoring"],
    ["evidence", "brain", "Evidence"]
  ];
  const modelLoaded = ["loaded", "loaded_local_fallback"].includes(modelInfo?.model_status || health?.model_status);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark small"><Icon name="dna" size={25} /></div>
          <div>
            <strong>GenoPredict</strong>
            <span>Variant review</span>
          </div>
        </div>
        <nav className="side-nav">
          {navItems.map(([key, icon, label]) => (
            <button key={key} className={page === key ? "active" : ""} onClick={() => setPage(key)} title={label}>
              <Icon name={icon} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button onClick={onExportHistory} disabled={!history.length}><Icon name="download" /> Export queue</button>
          <button onClick={onClearHistory} disabled={!history.length}><Icon name="alert" /> Clear queue</button>
          <button onClick={onLogout}><Icon name="logOut" /> Sign out</button>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Clinical decision-support demo</p>
            <h1>{navItems.find(([key]) => key === page)?.[2] || "Dashboard"}</h1>
          </div>
          <div className="topbar-status">
            <StatusPill tone={health?.api_status === "healthy" ? "green" : "amber"}>API {health?.api_status || "unknown"}</StatusPill>
            <StatusPill tone={modelLoaded ? "green" : "amber"}>Model {modelInfo?.model_status || health?.model_status || "unknown"}</StatusPill>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

function PageOverview({ health, modelInfo, history, visibleHistory, dashboard, historySearch, setHistorySearch, historyStatus, setHistoryStatus, onSetReviewStatus, onOpenPredict }) {
  const reviewCounts = REVIEW_STATUSES.map((status) => ({
    status,
    count: history.filter((row) => (row.reviewStatus || "Needs review") === status).length
  }));

  return (
    <div className="view-stack">
      <section className="hero-band">
        <div>
          <p className="eyebrow">Operational variant triage</p>
          <h2>Review predictions with evidence, provenance, and monitoring in one place.</h2>
          <p>Use this console to prioritize variants, export evidence reports, and keep model behavior observable.</p>
        </div>
        <button className="btn-primary-modern" onClick={onOpenPredict}><Icon name="search" /> New prediction</button>
      </section>

      <div className="metric-grid">
        <StatCard icon="file" label="Review queue" value={dashboard.total} subtext={`${dashboard.pathogenic} pathogenic predictions`} tone="blue" />
        <StatCard icon="activity" label="Pathogenic rate" value={`${dashboard.pathogenicRate.toFixed(1)}%`} subtext="Local review history" tone="red" />
        <StatCard icon="brain" label="Average probability" value={`${dashboard.avgProbability.toFixed(1)}%`} subtext="Predicted cases only" tone="violet" />
        <StatCard icon="shield" label="Model status" value={health?.model_status || "unknown"} subtext={modelInfo?.model_name || "GenomicVariantModel"} tone="green" />
      </div>

      <section className="content-grid two-one">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Lab Review Queue</h3>
              <p>Filter, assign review status, and export records for follow-up.</p>
            </div>
            <StatusPill>{visibleHistory.length} shown</StatusPill>
          </div>
          <div className="filter-row">
            <input placeholder="Search variant, source, or label" value={historySearch} onChange={(e) => setHistorySearch(e.target.value)} />
            <select value={historyStatus} onChange={(e) => setHistoryStatus(e.target.value)}>
              <option value="all">All review statuses</option>
              {REVIEW_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </div>
          <div className="table-wrap">
            <table className="modern-table">
              <thead>
                <tr>
                  <th>Variant</th>
                  <th>Prediction</th>
                  <th>Triage</th>
                  <th>Probability</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {visibleHistory.length === 0 ? (
                  <tr><td colSpan="5"><EmptyState title="No predictions yet" text="Run a single variant or VCF batch to start the review queue." /></td></tr>
                ) : (
                  visibleHistory.slice(0, 12).map((row) => (
                    <tr key={row.id}>
                      <td>
                        <strong>{row.variant}</strong>
                        <span>{row.source} | {row.timestamp}</span>
                      </td>
                      <td><StatusPill tone={row.label === "PATHOGENIC" ? "red" : "green"}>{row.label}</StatusPill></td>
                      <td>{triageLabel(row)}</td>
                      <td>{pct(row.probability, 1)}</td>
                      <td>
                        <select value={row.reviewStatus || "Needs review"} onChange={(e) => onSetReviewStatus(row.id, e.target.value)}>
                          {REVIEW_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                        </select>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="panel">
          <div className="panel-head">
            <div>
              <h3>Queue Summary</h3>
              <p>Current local review state.</p>
            </div>
          </div>
          <div className="review-list">
            {reviewCounts.map((item) => (
              <div key={item.status}>
                <span>{item.status}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
          <div className="divider" />
          <h4>Model provenance</h4>
          <p className="small-copy text-break">{modelInfo?.model_uri || "Model URI unavailable"}</p>
          <div className="mini-tags">
            <StatusPill tone="blue">{modelInfo?.input_features?.length || 0} features</StatusPill>
            <StatusPill tone="green">{modelInfo?.model_status || "unknown"}</StatusPill>
          </div>
        </aside>
      </section>
    </div>
  );
}

function PagePredict({ form, setForm, modelInfo, lookupStatus, lookupMessage, lookupLoading, predictLoading, fetchedRow, lastPrediction, onLookup, onPredict, onLoadDemoVariant, onReset }) {
  const drivers = getFeatureDrivers(lastPrediction?.features || form);
  const modelFallback = modelInfo?.model_status === "loaded_local_fallback";

  return (
    <div className="content-grid predict-grid">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>Single Variant Workbench</h3>
            <p>Resolve feature-store evidence first, then score the variant and export an evidence report.</p>
          </div>
          <button className="icon-button" onClick={onLoadDemoVariant} title="Load demo variant"><Icon name="database" /></button>
        </div>
        {modelFallback && <div className="inline-warning"><Icon name="alert" /> Model is running from local fallback. Check registry provenance before reporting.</div>}

        <div className="form-section">
          <h4>Variant identity</h4>
          <div className="form-grid identity-grid">
            <label>Chrom<select value={form.chrom} onChange={(e) => setForm((s) => ({ ...s, chrom: e.target.value }))}>{CHROMS.map((chrom) => <option key={chrom} value={chrom}>{chrom}</option>)}</select></label>
            <label>Position<input value={form.pos} onChange={(e) => setForm((s) => ({ ...s, pos: e.target.value }))} /></label>
            <label>REF<input value={form.ref} onChange={(e) => setForm((s) => ({ ...s, ref: e.target.value.toUpperCase() }))} /></label>
            <label>ALT<input value={form.alt} onChange={(e) => setForm((s) => ({ ...s, alt: e.target.value.toUpperCase() }))} /></label>
            <button className="btn-secondary-modern" onClick={onLookup} disabled={lookupLoading}><Icon name="search" /> {lookupLoading ? "Searching" : "Lookup"}</button>
          </div>
          {lookupStatus === "found" && <div className="inline-success"><Icon name="check" /> Variant found in feature store. Manual evidence was filled automatically.</div>}
          {lookupStatus === "not_found" && <div className="inline-warning"><Icon name="alert" /> Variant not found. Fill all annotation values before scoring.</div>}
          {lookupStatus === "error" && <div className="inline-error">{lookupMessage}</div>}
        </div>

        <div className="form-section">
          <h4>Annotation evidence</h4>
          <div className="form-grid evidence-grid">
            <label>SIFT<input type="number" min="0" max="1" step="0.001" value={form.sift} onChange={(e) => setForm((s) => ({ ...s, sift: e.target.value }))} /></label>
            <label>PolyPhen<input type="number" min="0" max="1" step="0.001" value={form.polyphen} onChange={(e) => setForm((s) => ({ ...s, polyphen: e.target.value }))} /></label>
            <label>CADD<input type="number" min="0" max="60" step="0.1" value={form.cadd} onChange={(e) => setForm((s) => ({ ...s, cadd: e.target.value }))} /></label>
            <label>ALT frequency<input type="number" min="0" max="1" step="0.000001" value={form.alt_freq} onChange={(e) => setForm((s) => ({ ...s, alt_freq: e.target.value }))} /></label>
          </div>
        </div>

        <div className="action-row">
          <button className="btn-primary-modern" onClick={onPredict} disabled={predictLoading}><Icon name="play" /> {predictLoading ? "Scoring" : "Run prediction"}</button>
          <button className="btn-ghost-modern" onClick={onReset}><Icon name="refresh" /> Reset</button>
        </div>
      </section>

      <aside className="panel result-panel">
        <div className="panel-head">
          <div>
            <h3>Evidence Report</h3>
            <p>Professional review output for the latest prediction.</p>
          </div>
        </div>
        {!lastPrediction ? (
          <EmptyState icon="file" title="No result yet" text="Score a variant to generate a triage summary and exportable evidence report." />
        ) : (
          <div className="result-card">
            <StatusPill tone={lastPrediction.label === "PATHOGENIC" ? "red" : "green"}>{lastPrediction.label}</StatusPill>
            <h2>{pct(lastPrediction.probability, 2)}</h2>
            <p>{lastPrediction.variant}</p>
            <div className="triage-box">
              <span>Triage</span>
              <strong>{triageLabel(lastPrediction)}</strong>
            </div>
            <div className="evidence-bars">
              {drivers.map((driver) => (
                <div key={driver.name}>
                  <div><strong>{driver.name}</strong><span>{driver.value} | {driver.direction}</span></div>
                  <div className="bar"><span style={{ width: `${driver.strength}%` }} /></div>
                </div>
              ))}
            </div>
            {lastPrediction.confidence < 0.6 && <div className="inline-warning"><Icon name="alert" /> Low confidence. Review feature completeness.</div>}
            <div className="action-row stacked">
              <button className="btn-secondary-modern" onClick={() => printReviewReport(lastPrediction, modelInfo)}><Icon name="print" /> Print / save PDF</button>
              <button className="btn-ghost-modern" onClick={() => exportReviewReport(lastPrediction, modelInfo)}><Icon name="download" /> Export text report</button>
            </div>
          </div>
        )}
        {fetchedRow && (
          <div className="fetched-preview">
            <h4>Fetched record</h4>
            <p>{String(fetchedRow["#chr"] ?? fetchedRow.CHROM)}:{String(fetchedRow["pos(1-based)"] ?? fetchedRow.POS)} {String(fetchedRow.ref ?? fetchedRow.REF)}&gt;{String(fetchedRow.alt ?? fetchedRow.ALT)}</p>
          </div>
        )}
      </aside>
    </div>
  );
}

function PageVcf({ onSelectVariant, onBatchResults }) {
  const [vcfFile, setVcfFile] = useState(null);
  const [limit, setLimit] = useState(200);
  const [loading, setLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [error, setError] = useState("");
  const [records, setRecords] = useState([]);
  const [batchSummary, setBatchSummary] = useState(null);
  const [batchResults, setBatchResults] = useState([]);
  const [batchFilter, setBatchFilter] = useState("all");
  const [batchSearch, setBatchSearch] = useState("");
  const [minConfidence, setMinConfidence] = useState(0);
  const [sortMode, setSortMode] = useState("probability_desc");

  const filteredBatchResults = useMemo(() => {
    const query = batchSearch.trim().toLowerCase();
    const minConf = Number(minConfidence) / 100;
    return [...batchResults]
      .filter((row) => {
        if (batchFilter === "pathogenic" && row.label !== "PATHOGENIC") return false;
        if (batchFilter === "benign" && row.label !== "BENIGN") return false;
        if (batchFilter === "predicted" && row.status !== "predicted") return false;
        if (batchFilter === "not_found" && row.status !== "not_found") return false;
        if (batchFilter === "failed" && row.status !== "failed") return false;
        if ((row.confidence_score ?? 0) < minConf) return false;
        if (!query) return true;
        return `${row.chrom}:${row.pos} ${row.ref}>${row.alt} ${row.status} ${row.label || ""}`.toLowerCase().includes(query);
      })
      .sort((a, b) => {
        if (sortMode === "confidence_desc") return (b.confidence_score ?? -1) - (a.confidence_score ?? -1);
        if (sortMode === "probability_asc") return (a.probability ?? 2) - (b.probability ?? 2);
        if (sortMode === "variant_asc") return variantLabel(a).localeCompare(variantLabel(b));
        return (b.probability ?? -1) - (a.probability ?? -1);
      });
  }, [batchResults, batchFilter, batchSearch, minConfidence, sortMode]);

  const handleUpload = async () => {
    setError("");
    if (!vcfFile) {
      setError("Please choose a VCF file first.");
      return;
    }
    setLoading(true);
    try {
      const response = await uploadVcf(vcfFile, limit);
      setRecords(response.records || []);
      setBatchResults([]);
      setBatchSummary(null);
      if (!response.records?.length) setError(response.message || "No records parsed from file.");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBatchPredict = async () => {
    setError("");
    if (!records.length) {
      setError("Parse a VCF file first.");
      return;
    }
    setBatchLoading(true);
    try {
      const response = await predictVcfBatch(records, limit);
      const summary = {
        processed: response.processed,
        predicted: response.predicted,
        notFound: response.not_found,
        failed: response.failed
      };
      setBatchSummary(summary);
      setBatchResults(response.results || []);
      onBatchResults?.(response.results || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleLoadDemoBatch = () => {
    setError("");
    setVcfFile(null);
    setRecords(DEMO_BATCH_RECORDS);
    setBatchResults([]);
    setBatchSummary(null);
  };

  return (
    <div className="view-stack">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>VCF Batch Review</h3>
            <p>Upload, preview, score, filter, and export a variant review report.</p>
          </div>
          <button className="btn-secondary-modern" onClick={handleLoadDemoBatch}><Icon name="database" /> Demo batch</button>
        </div>
        <div className="upload-zone">
          <Icon name="upload" size={34} />
          <div>
            <strong>{vcfFile?.name || "Choose a .vcf or .vcf.gz file"}</strong>
            <span>Sample files live in data/examples.</span>
          </div>
          <input type="file" accept=".vcf,.vcf.gz" onChange={(e) => setVcfFile(e.target.files?.[0] || null)} />
        </div>
        <div className="filter-row">
          <label>Max records<input type="number" min="1" max="5000" value={limit} onChange={(e) => setLimit(Math.max(1, Math.min(5000, Number(e.target.value) || 1)))} /></label>
          <button className="btn-secondary-modern" onClick={handleUpload} disabled={loading}><Icon name="file" /> {loading ? "Parsing" : "Parse VCF"}</button>
          <button className="btn-primary-modern" onClick={handleBatchPredict} disabled={batchLoading || !records.length}><Icon name="play" /> {batchLoading ? "Scoring" : "Run batch"}</button>
        </div>
        {error && <div className="inline-error">{error}</div>}
        {batchSummary && (
          <div className="batch-summary">
            <StatCard icon="file" label="Processed" value={batchSummary.processed} tone="blue" />
            <StatCard icon="check" label="Predicted" value={batchSummary.predicted} tone="green" />
            <StatCard icon="search" label="Not found" value={batchSummary.notFound} tone="amber" />
            <StatCard icon="alert" label="Failed" value={batchSummary.failed} tone="red" />
          </div>
        )}
      </section>

      <section className="content-grid two-one">
        <div className="panel">
          <div className="panel-head"><h3>Parsed Variants</h3><StatusPill>{records.length} records</StatusPill></div>
          <div className="table-wrap">
            <table className="modern-table">
              <thead><tr><th>Variant</th><th>REF</th><th>ALT</th><th>Action</th></tr></thead>
              <tbody>
                {records.length === 0 ? (
                  <tr><td colSpan="4"><EmptyState icon="upload" title="No parsed records" text="Parse a VCF file or load the demo batch." /></td></tr>
                ) : records.slice(0, 12).map((row, idx) => (
                  <tr key={`${row.chrom}-${row.pos}-${row.ref}-${row.alt}-${idx}`}>
                    <td><strong>{row.chrom}:{row.pos}</strong></td>
                    <td>{row.ref}</td>
                    <td>{row.alt}</td>
                    <td><button className="table-action" onClick={() => onSelectVariant(row)}>Use in Variant</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <aside className="panel">
          <h3>Batch Controls</h3>
          <div className="form-section compact">
            <label>Search results<input value={batchSearch} onChange={(e) => setBatchSearch(e.target.value)} placeholder="Variant, status, label" /></label>
            <label>Status<select value={batchFilter} onChange={(e) => setBatchFilter(e.target.value)}>
              <option value="all">All results</option>
              <option value="predicted">Predicted only</option>
              <option value="pathogenic">Pathogenic only</option>
              <option value="benign">Benign only</option>
              <option value="not_found">Not found</option>
              <option value="failed">Failed</option>
            </select></label>
            <label>Sort<select value={sortMode} onChange={(e) => setSortMode(e.target.value)}>
              <option value="probability_desc">Probability high to low</option>
              <option value="probability_asc">Probability low to high</option>
              <option value="confidence_desc">Confidence high to low</option>
              <option value="variant_asc">Variant A to Z</option>
            </select></label>
            <label>Min confidence<input type="number" min="0" max="100" value={minConfidence} onChange={(e) => setMinConfidence(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} /></label>
          </div>
          <button className="btn-secondary-modern full" disabled={!batchResults.length} onClick={() => exportBatchReportCSV(batchSummary, filteredBatchResults)}><Icon name="download" /> Export filtered report</button>
        </aside>
      </section>

      {batchResults.length > 0 && (
        <section className="panel">
          <div className="panel-head"><h3>Batch Results</h3><StatusPill>{filteredBatchResults.length} shown</StatusPill></div>
          <div className="table-wrap">
            <table className="modern-table">
              <thead><tr><th>Variant</th><th>Status</th><th>Prediction</th><th>Triage</th><th>Probability</th><th>Confidence</th><th>Message</th></tr></thead>
              <tbody>
                {filteredBatchResults.map((row, idx) => (
                  <tr key={`${row.chrom}-${row.pos}-${row.ref}-${row.alt}-batch-${idx}`}>
                    <td><strong>{row.chrom}:{row.pos}</strong><span>{row.ref}&gt;{row.alt}</span></td>
                    <td><StatusPill tone={row.status === "predicted" ? "green" : row.status === "not_found" ? "amber" : "red"}>{row.status}</StatusPill></td>
                    <td>{row.label ? <StatusPill tone={row.label === "PATHOGENIC" ? "red" : "green"}>{row.label}</StatusPill> : "N/A"}</td>
                    <td>{row.label ? triageLabel({ label: row.label, probability: row.probability, confidence: row.confidence_score }) : "N/A"}</td>
                    <td>{pct(row.probability, 2)}</td>
                    <td>{pct(row.confidence_score, 2)}</td>
                    <td>{row.message || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function PageMonitoring({ summary, drift, events, loading, onRefresh }) {
  const latestEvents = events?.items || [];
  const grafanaUrl = `${window.location.protocol}//${window.location.hostname}:3001`;
  const prometheusUrl = `${window.location.protocol}//${window.location.hostname}:9090`;
  const metricsUrl = `${window.location.origin}/metrics`;
  const driftFeatures = drift?.features || [];
  const driftScore = typeof drift?.drift_score === "number" ? drift.drift_score : null;

  return (
    <div className="view-stack">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>Runtime Monitoring</h3>
            <p>Track model health, drift status, prediction history, and operations endpoints.</p>
          </div>
          <button className="btn-secondary-modern" onClick={onRefresh} disabled={loading}><Icon name="refresh" /> {loading ? "Refreshing" : "Refresh"}</button>
        </div>
        <div className="metric-grid">
          <StatCard icon="activity" label="Logged events" value={summary?.total_predictions ?? 0} tone="blue" />
          <StatCard icon="brain" label="Pathogenic rate" value={pct(summary?.pathogenic_rate)} tone="red" />
          <StatCard icon="shield" label="Avg confidence" value={pct(summary?.average_confidence)} tone="green" />
          <StatCard icon="activity" label="Avg latency" value={`${fmt(summary?.average_latency_ms)} ms`} tone="violet" />
        </div>
      </section>

      <section className="content-grid two-one">
        <div className="panel">
          <div className="panel-head"><h3>Feature Drift</h3><StatusPill tone={driftScore && driftScore > 0 ? "amber" : "green"}>{drift?.status || "not_available"}</StatusPill></div>
          <div className="table-wrap">
            <table className="modern-table">
              <thead><tr><th>Feature</th><th>Status</th><th>Reference</th><th>Current</th><th>Delta</th><th>Threshold</th></tr></thead>
              <tbody>
                {driftFeatures.length === 0 ? (
                  <tr><td colSpan="6"><EmptyState icon="activity" title="No drift summary" text={drift?.message || "Run predictions and drift checks to populate this view."} /></td></tr>
                ) : driftFeatures.map((row) => (
                  <tr key={row.feature}>
                    <td><strong>{row.feature}</strong></td>
                    <td><StatusPill tone={row.drifted ? "red" : "green"}>{row.drifted ? "Drifted" : "Stable"}</StatusPill></td>
                    <td>{fmt(row.reference_mean, 4)}</td>
                    <td>{fmt(row.current_mean, 4)}</td>
                    <td>{fmt(row.mean_delta, 4)}</td>
                    <td>{fmt(row.threshold, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <aside className="panel">
          <h3>Operations</h3>
          <div className="review-list">
            <div><span>API</span><strong>{summary?.api_status || "unknown"}</strong></div>
            <div><span>Model</span><strong>{summary?.model_status || "unknown"}</strong></div>
            <div><span>Failures</span><strong>{summary?.failed_predictions ?? 0}</strong></div>
            <div><span>Low confidence</span><strong>{summary?.low_confidence_predictions ?? 0}</strong></div>
          </div>
          <div className="action-row stacked mt-3">
            <a className="btn-secondary-modern" href={grafanaUrl} target="_blank" rel="noreferrer">Open Grafana</a>
            <a className="btn-secondary-modern" href={prometheusUrl} target="_blank" rel="noreferrer">Open Prometheus</a>
            <a className="btn-ghost-modern" href={metricsUrl} target="_blank" rel="noreferrer">Raw metrics</a>
          </div>
        </aside>
      </section>

      <section className="panel">
        <div className="panel-head"><h3>Recent Events</h3><StatusPill>{latestEvents.length} events</StatusPill></div>
        <div className="table-wrap">
          <table className="modern-table">
            <thead><tr><th>Time</th><th>Endpoint</th><th>Variant</th><th>Status</th><th>Prediction</th><th>Confidence</th><th>Latency</th></tr></thead>
            <tbody>
              {latestEvents.length === 0 ? (
                <tr><td colSpan="7"><EmptyState title="No monitoring events" text="Run predictions to populate event logs." /></td></tr>
              ) : latestEvents.map((row, idx) => (
                <tr key={`${row.timestamp}-${idx}`}>
                  <td>{row.timestamp ? new Date(row.timestamp).toLocaleString() : "N/A"}</td>
                  <td>{row.endpoint || "unknown"}</td>
                  <td>{row.chrom && row.pos ? `${row.chrom}:${row.pos} ${row.ref || ""}>${row.alt || ""}` : "N/A"}</td>
                  <td><StatusPill tone={row.status === "success" ? "green" : "red"}>{row.status || "unknown"}</StatusPill></td>
                  <td>{row.prediction === 1 ? "PATHOGENIC" : row.prediction === 0 ? "BENIGN" : "N/A"}</td>
                  <td>{pct(row.confidence_score)}</td>
                  <td>{fmt(row.latency_ms)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function PageEvidence({ modelInfo }) {
  const features = modelInfo?.input_features || [];
  return (
    <div className="view-stack">
      <section className="hero-band evidence-hero">
        <div>
          <p className="eyebrow">Model evidence</p>
          <h2>Annotation-driven prioritization with model provenance and explainability.</h2>
          <p>The model aggregates SIFT, PolyPhen, CADD, population frequency, and engineered genomic context into an operational triage workflow.</p>
        </div>
        <StatusPill tone={modelInfo?.model_status === "loaded" ? "green" : "amber"}>{modelInfo?.model_status || "unknown"}</StatusPill>
      </section>

      <section className="content-grid split">
        <div className="panel">
          <div className="panel-head"><h3>SHAP Feature Importance</h3></div>
          <img className="explainability-plot" src="/figures/shap_bar_plot.png" alt="SHAP bar plot showing global feature importance" />
        </div>
        <div className="panel">
          <div className="panel-head"><h3>SHAP Summary</h3></div>
          <img className="explainability-plot explainability-plot-tall" src="/figures/shap_summary_plot.png" alt="SHAP summary plot showing feature effects across samples" />
        </div>
      </section>

      <section className="panel">
        <div className="panel-head"><h3>Feature Contract</h3><StatusPill>{features.length} features</StatusPill></div>
        {features.length === 0 ? <EmptyState title="Feature metadata unavailable" text="The API has not returned model feature metadata yet." /> : (
          <div className="feature-chip-grid">
            {features.map((feature, idx) => <span key={feature} className="feature-chip"><small>{idx + 1}</small>{feature}</span>)}
          </div>
        )}
      </section>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(() => sessionStorage.getItem(AUTH_KEY) === "true");
  const [page, setPage] = useState("overview");
  const [form, setForm] = useState(INITIAL_FORM);
  const [health, setHealth] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [appError, setAppError] = useState("");
  const [lookupStatus, setLookupStatus] = useState("idle");
  const [lookupMessage, setLookupMessage] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [predictLoading, setPredictLoading] = useState(false);
  const [monitoringLoading, setMonitoringLoading] = useState(false);
  const [monitoringSummary, setMonitoringSummary] = useState(null);
  const [monitoringDrift, setMonitoringDrift] = useState(null);
  const [monitoringEvents, setMonitoringEvents] = useState({ items: [] });
  const [fetchedRow, setFetchedRow] = useState(null);
  const [lastPrediction, setLastPrediction] = useState(null);
  const [historySearch, setHistorySearch] = useState("");
  const [historyStatus, setHistoryStatus] = useState("all");
  const [history, setHistory] = useState(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    try {
      return JSON.parse(raw);
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    if (!authed) return;
    const loadMeta = async () => {
      try {
        const [healthRes, infoRes] = await Promise.all([getHealth(), getModelInfo()]);
        setHealth(healthRes);
        setModelInfo(infoRes);
      } catch (e) {
        setAppError(e.message);
      }
    };
    loadMeta();
  }, [authed]);

  const loadMonitoring = async () => {
    setMonitoringLoading(true);
    try {
      const [summaryRes, driftRes, eventsRes] = await Promise.all([
        getMonitoringSummary(),
        getMonitoringDrift(),
        getMonitoringPredictions(50)
      ]);
      setMonitoringSummary(summaryRes);
      setMonitoringDrift(driftRes);
      setMonitoringEvents(eventsRes);
    } catch (e) {
      setAppError(e.message);
    } finally {
      setMonitoringLoading(false);
    }
  };

  useEffect(() => {
    if (authed) loadMonitoring();
  }, [authed]);

  const dashboard = useMemo(() => {
    const total = history.length;
    const pathogenic = history.filter((row) => row.label === "PATHOGENIC").length;
    const pathogenicRate = total ? (pathogenic / total) * 100 : 0;
    const withProba = history.filter((row) => row.probability !== null && row.probability !== undefined);
    const avgProbability = withProba.length ? (withProba.reduce((acc, row) => acc + row.probability, 0) / withProba.length) * 100 : 0;
    return { total, pathogenic, pathogenicRate, avgProbability };
  }, [history]);

  const visibleHistory = useMemo(() => {
    const query = historySearch.trim().toLowerCase();
    return history.filter((row) => {
      const status = row.reviewStatus || "Needs review";
      if (historyStatus !== "all" && status !== historyStatus) return false;
      if (!query) return true;
      return `${row.variant} ${row.source} ${row.label} ${status}`.toLowerCase().includes(query);
    });
  }, [history, historySearch, historyStatus]);

  const handleLookup = async () => {
    setAppError("");
    setLookupLoading(true);
    setLookupStatus("idle");
    setLookupMessage("");
    setFetchedRow(null);
    try {
      const response = await fetchFeatures({
        chrom: form.chrom,
        pos: form.pos,
        ref: form.ref.trim().toUpperCase(),
        alt: form.alt.trim().toUpperCase()
      });
      if (!response.found || !response.data?.length) {
        setLookupStatus("not_found");
        setLookupMessage(response.message || "Variant not found in feature store.");
      } else {
        const normalized = normalizeFetchedRow(response.data[0], form);
        setForm((prev) => ({ ...prev, ...normalized }));
        setFetchedRow(response.data[0]);
        setLookupStatus("found");
        setLookupMessage("Variant found in feature store.");
      }
    } catch (e) {
      setLookupStatus("error");
      setLookupMessage(e.message);
    } finally {
      setLookupLoading(false);
    }
  };

  const handlePredict = async () => {
    setAppError("");
    if (!form.chrom || !form.pos || !form.ref.trim() || !form.alt.trim()) {
      setAppError("Please fill chrom, pos, ref, and alt.");
      return;
    }
    if (lookupStatus !== "found" && !isManualSpecsComplete(form)) {
      setAppError("Variant not found in database: SIFT, PolyPhen, CADD, and ALT_FREQ are required.");
      return;
    }
    setPredictLoading(true);
    try {
      const payload = buildPredictionPayload(form);
      const response = await predictVariant(payload);
      const row = {
        id: Date.now(),
        timestamp: new Date().toLocaleString(),
        chrom: payload.chrom,
        variant: `${payload.chrom}:${payload.pos} ${payload.ref}>${payload.alt}`,
        source: lookupStatus === "found" ? "Feature Store" : "Manual",
        label: labelFromPrediction(response.prediction),
        probability: response.probability ?? null,
        confidence: response.confidence_score ?? 0.5,
        reviewStatus: "Needs review",
        features: {
          sift: payload.sift ?? "",
          polyphen: payload.polyphen ?? "",
          cadd: payload.cadd ?? "",
          alt_freq: payload.alt_freq ?? ""
        },
        modelName: modelInfo?.model_name || "GenomicVariantModel",
        modelUri: modelInfo?.model_uri || "models:/GenomicVariantModel@Production"
      };
      setLastPrediction(row);
      setHistory((prev) => [row, ...prev].slice(0, 200));
      loadMonitoring();
      setPage("overview");
    } catch (e) {
      setAppError(e.message);
    } finally {
      setPredictLoading(false);
    }
  };

  const handleReset = () => {
    setForm(INITIAL_FORM);
    setLookupStatus("idle");
    setLookupMessage("");
    setFetchedRow(null);
    setAppError("");
  };

  const handleLoadDemoVariant = () => {
    setForm(INITIAL_FORM);
    setLookupStatus("idle");
    setLookupMessage("");
    setFetchedRow(null);
    setAppError("");
  };

  const handleSetReviewStatus = (id, reviewStatus) => {
    setHistory((prev) => prev.map((row) => (row.id === id ? { ...row, reviewStatus } : row)));
    if (lastPrediction?.id === id) setLastPrediction((prev) => (prev ? { ...prev, reviewStatus } : prev));
  };

  const handleSelectVcfVariant = (row) => {
    setForm((prev) => ({
      ...prev,
      chrom: String(row.chrom),
      pos: String(row.pos),
      ref: String(row.ref).toUpperCase(),
      alt: String(row.alt).toUpperCase()
    }));
    setLookupStatus("idle");
    setLookupMessage("");
    setFetchedRow(null);
    setPage("predict");
  };

  const handleBatchResults = (results) => {
    const predictedRows = (results || []).filter((row) => row.status === "predicted");
    if (!predictedRows.length) return;
    const now = Date.now();
    const newHistory = predictedRows.map((row, idx) => ({
      id: now + idx,
      timestamp: new Date().toLocaleString(),
      chrom: String(row.chrom),
      variant: `${row.chrom}:${row.pos} ${row.ref}>${row.alt}`,
      source: "VCF Batch",
      label: row.label || labelFromPrediction(row.prediction),
      probability: row.probability ?? null,
      confidence: row.confidence_score ?? 0.5,
      reviewStatus: "Needs review",
      features: {},
      modelName: modelInfo?.model_name || "GenomicVariantModel",
      modelUri: modelInfo?.model_uri || "models:/GenomicVariantModel@Production"
    }));
    setHistory((prev) => [...newHistory, ...prev].slice(0, 200));
    loadMonitoring();
  };

  const logout = () => {
    sessionStorage.removeItem(AUTH_KEY);
    setAuthed(false);
  };

  if (!authed) return <LoginScreen onLogin={() => setAuthed(true)} />;

  return (
    <AppShell
      page={page}
      setPage={setPage}
      health={health}
      modelInfo={modelInfo}
      history={history}
      onLogout={logout}
      onExportHistory={() => exportHistoryCSV(history)}
      onClearHistory={() => setHistory([])}
    >
      {appError && <div className="app-alert"><Icon name="alert" /> {appError}</div>}
      <div className="page-transition" key={page}>
        {page === "overview" && (
          <PageOverview
            health={health}
            modelInfo={modelInfo}
            history={history}
            visibleHistory={visibleHistory}
            dashboard={dashboard}
            historySearch={historySearch}
            setHistorySearch={setHistorySearch}
            historyStatus={historyStatus}
            setHistoryStatus={setHistoryStatus}
            onSetReviewStatus={handleSetReviewStatus}
            onOpenPredict={() => setPage("predict")}
          />
        )}
        {page === "predict" && (
          <PagePredict
            form={form}
            setForm={setForm}
            modelInfo={modelInfo}
            lookupStatus={lookupStatus}
            lookupMessage={lookupMessage}
            lookupLoading={lookupLoading}
            predictLoading={predictLoading}
            fetchedRow={fetchedRow}
            lastPrediction={lastPrediction}
            onLookup={handleLookup}
            onPredict={handlePredict}
            onLoadDemoVariant={handleLoadDemoVariant}
            onReset={handleReset}
          />
        )}
        {page === "vcf" && <PageVcf onSelectVariant={handleSelectVcfVariant} onBatchResults={handleBatchResults} />}
        {page === "monitoring" && <PageMonitoring summary={monitoringSummary} drift={monitoringDrift} events={monitoringEvents} loading={monitoringLoading} onRefresh={loadMonitoring} />}
        {page === "evidence" && <PageEvidence modelInfo={modelInfo} />}
      </div>
    </AppShell>
  );
}
