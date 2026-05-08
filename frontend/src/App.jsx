import { useEffect, useMemo, useState } from "react";
import {
  fetchFeatures,
  getHealth,
  getModelInfo,
  getMonitoringPredictions,
  getMonitoringSummary,
  predictVariant,
  predictVcfBatch,
  uploadVcf
} from "./api";

const CHROMS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "X", "Y", "M"];
const STORAGE_KEY = "genopredict_prediction_history_v2";

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

function toNumber(value) {
  if (value === undefined || value === null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function labelFromPrediction(prediction) {
  return Number(prediction) === 1 ? "PATHOGENIC" : "BENIGN";
}

function extractNumeric(row, candidates, fallback = "") {
  for (const key of candidates) {
    if (row[key] !== undefined && row[key] !== null && row[key] !== "") {
      return String(row[key]);
    }
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
  const base = {
    chrom: form.chrom,
    pos: String(form.pos).trim(),
    ref: String(form.ref).trim().toUpperCase(),
    alt: String(form.alt).trim().toUpperCase()
  };
  const numeric = {
    sift: toNumber(form.sift),
    polyphen: toNumber(form.polyphen),
    cadd: toNumber(form.cadd),
    alt_freq: toNumber(form.alt_freq)
  };

  for (const [key, value] of Object.entries(numeric)) {
    if (value !== null) base[key] = value;
  }
  return base;
}

function isManualSpecsComplete(form) {
  return (
    toNumber(form.sift) !== null &&
    toNumber(form.polyphen) !== null &&
    toNumber(form.cadd) !== null &&
    toNumber(form.alt_freq) !== null
  );
}

function exportHistoryCSV(history) {
  if (!history.length) return;
  const headers = ["timestamp", "variant", "source", "prediction", "probability_percent", "confidence_percent"];
  const lines = [headers.join(",")];
  for (const row of history) {
    const prob = row.probability === null || row.probability === undefined ? "" : (row.probability * 100).toFixed(3);
    const conf = row.confidence === null || row.confidence === undefined ? "" : (row.confidence * 100).toFixed(3);
    const cells = [row.timestamp, row.variant, row.source, row.label, prob, conf];
    lines.push(cells.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","));
  }

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "genopredict_history.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function exportBatchReportCSV(summary, rows) {
  if (!rows.length) return;

  const headers = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "status",
    "prediction",
    "label",
    "probability_percent",
    "confidence_percent",
    "message",
    "processed",
    "predicted",
    "not_found",
    "failed"
  ];

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

function PageOverview({ health, modelInfo, history, dashboard }) {
  return (
    <div className="page-panel">
      <div className="row g-3 mb-3">
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Total Predictions</h6>
              <h2 className="mb-0">{dashboard.total}</h2>
            </div>
          </div>
        </div>
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Pathogenic Rate</h6>
              <h2 className="mb-2">{dashboard.pathogenicRate.toFixed(1)}%</h2>
              <div className="progress">
                <div className="progress-bar bg-danger" style={{ width: `${dashboard.pathogenicRate}%` }} />
              </div>
            </div>
          </div>
        </div>
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Avg Probability</h6>
              <h2 className="mb-0">{dashboard.avgProbability.toFixed(1)}%</h2>
            </div>
          </div>
        </div>
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Model Status</h6>
              <h2 className={`mb-0 ${health?.model_status === "loaded" ? "text-success" : "text-warning"}`}>
                {health?.model_status || "unknown"}
              </h2>
            </div>
          </div>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-xl-8">
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white border-0 py-3 d-flex justify-content-between align-items-center">
              <h5 className="mb-0">Recent Predictions</h5>
              <span className="badge text-bg-light">{history.length} stored</span>
            </div>
            <div className="table-responsive">
              <table className="table table-striped table-hover mb-0 align-middle">
                <thead className="table-light">
                  <tr>
                    <th>Time</th>
                    <th>Variant</th>
                    <th>Source</th>
                    <th>Prediction</th>
                    <th>Probability</th>
                  </tr>
                </thead>
                <tbody>
                  {history.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="text-center text-secondary py-4">
                        No predictions yet.
                      </td>
                    </tr>
                  ) : (
                    history.slice(0, 10).map((row) => (
                      <tr key={row.id}>
                        <td>{row.timestamp}</td>
                        <td>{row.variant}</td>
                        <td>{row.source}</td>
                        <td>
                          <span className={`badge ${row.label === "PATHOGENIC" ? "text-bg-danger" : "text-bg-success"}`}>
                            {row.label}
                          </span>
                        </td>
                        <td>{row.probability !== null ? `${(row.probability * 100).toFixed(1)}%` : "N/A"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="col-xl-4">
          <div className="card shadow-sm border-0 mb-3">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">Top Chromosomes</h5>
            </div>
            <div className="card-body">
              {dashboard.byChrom.length === 0 ? (
                <p className="text-secondary mb-0">No data yet.</p>
              ) : (
                dashboard.byChrom.map(([chrom, count]) => {
                  const width = dashboard.total ? (count / dashboard.total) * 100 : 0;
                  return (
                    <div key={chrom} className="mb-2">
                      <div className="d-flex justify-content-between small">
                        <span>Chr {chrom}</span>
                        <span>{count}</span>
                      </div>
                      <div className="progress">
                        <div className="progress-bar" style={{ width: `${width}%` }} />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="card shadow-sm border-0">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">System Snapshot</h5>
            </div>
            <div className="card-body">
              <p className="mb-2"><span className="fw-semibold">API:</span> {health?.api_status || "unknown"}</p>
              <p className="mb-2"><span className="fw-semibold">Model:</span> {modelInfo?.model_name || "unknown"}</p>
              <p className="mb-2"><span className="fw-semibold">Registry URI:</span> {modelInfo?.model_uri || "not loaded"}</p>
              <p className="mb-0"><span className="fw-semibold">Feature Count:</span> {modelInfo?.input_features?.length || 0}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PagePredict({
  form,
  setForm,
  lookupStatus,
  lookupMessage,
  lookupLoading,
  predictLoading,
  fetchedRow,
  lastPrediction,
  onLookup,
  onPredict,
  onReset
}) {
  return (
    <div className="page-panel">
      <div className="row g-3">
        <div className="col-xl-8">
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">Variant Prediction Workbench</h5>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-2">
                  <label className="form-label">Chrom</label>
                  <select className="form-select" value={form.chrom} onChange={(e) => setForm((s) => ({ ...s, chrom: e.target.value }))}>
                    {CHROMS.map((chrom) => (
                      <option key={chrom} value={chrom}>{chrom}</option>
                    ))}
                  </select>
                </div>
                <div className="col-md-3">
                  <label className="form-label">Position</label>
                  <input className="form-control" value={form.pos} onChange={(e) => setForm((s) => ({ ...s, pos: e.target.value }))} />
                </div>
                <div className="col-md-2">
                  <label className="form-label">REF</label>
                  <input className="form-control text-uppercase" value={form.ref} onChange={(e) => setForm((s) => ({ ...s, ref: e.target.value }))} />
                </div>
                <div className="col-md-2">
                  <label className="form-label">ALT</label>
                  <input className="form-control text-uppercase" value={form.alt} onChange={(e) => setForm((s) => ({ ...s, alt: e.target.value }))} />
                </div>
                <div className="col-md-3 d-flex align-items-end">
                  <button className="btn btn-outline-primary w-100" onClick={onLookup} disabled={lookupLoading}>
                    {lookupLoading ? "Searching..." : "Lookup Feature Store"}
                  </button>
                </div>
              </div>

              <div className="mt-3">
                {lookupStatus === "found" && <div className="alert alert-success py-2 mb-0">Variant found in database. Manual specs are optional.</div>}
                {lookupStatus === "not_found" && <div className="alert alert-warning py-2 mb-0">Variant not found. Please fill all manual specs before prediction.</div>}
                {lookupStatus === "error" && <div className="alert alert-danger py-2 mb-0">{lookupMessage}</div>}
              </div>

              <hr />

              <div className="row g-2">
                <div className="col-md-3">
                  <label className="form-label">SIFT</label>
                  <input className="form-control" value={form.sift} onChange={(e) => setForm((s) => ({ ...s, sift: e.target.value }))} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">PolyPhen</label>
                  <input className="form-control" value={form.polyphen} onChange={(e) => setForm((s) => ({ ...s, polyphen: e.target.value }))} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">CADD</label>
                  <input className="form-control" value={form.cadd} onChange={(e) => setForm((s) => ({ ...s, cadd: e.target.value }))} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">ALT Freq</label>
                  <input className="form-control" value={form.alt_freq} onChange={(e) => setForm((s) => ({ ...s, alt_freq: e.target.value }))} />
                </div>
              </div>

              <div className="d-flex gap-2 mt-3">
                <button className="btn btn-success" onClick={onPredict} disabled={predictLoading}>
                  {predictLoading ? "Predicting..." : "Run Prediction"}
                </button>
                <button className="btn btn-outline-secondary" onClick={onReset}>
                  Reset
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="col-xl-4">
          <div className="card shadow-sm border-0 mb-3">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">Latest Result</h5>
            </div>
            <div className="card-body">
              {!lastPrediction ? (
                <p className="text-secondary mb-0">Run a prediction to see output.</p>
              ) : (
                <>
                  <h4 className={lastPrediction.label === "PATHOGENIC" ? "text-danger" : "text-success"}>
                    {lastPrediction.label}
                  </h4>
                  <p className="mb-2 fw-semibold">{lastPrediction.variant}</p>
                  <p className="mb-1">Probability: {lastPrediction.probability !== null ? `${(lastPrediction.probability * 100).toFixed(2)}%` : "N/A"}</p>
                  <p className="mb-1">Confidence: {(lastPrediction.confidence * 100).toFixed(2)}%</p>
                  <p className="mb-0 text-secondary">Source: {lastPrediction.source}</p>
                </>
              )}
            </div>
          </div>

          {fetchedRow && (
            <div className="card shadow-sm border-0">
              <div className="card-header bg-white border-0 py-3">
                <h5 className="mb-0">Fetched Record Preview</h5>
              </div>
              <div className="card-body">
                <div className="small">
                  <div><span className="text-secondary">Variant:</span> {String(fetchedRow["#chr"] ?? fetchedRow.CHROM)}:{String(fetchedRow["pos(1-based)"] ?? fetchedRow.POS)}</div>
                  <div><span className="text-secondary">REF/ALT:</span> {String(fetchedRow.ref ?? fetchedRow.REF)} / {String(fetchedRow.alt ?? fetchedRow.ALT)}</div>
                  <div><span className="text-secondary">CADD:</span> {String(fetchedRow.CADD_phred ?? fetchedRow.CADD ?? "N/A")}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
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
      if (!response.records?.length) {
        setError(response.message || "No records parsed from file.");
      }
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
      setBatchSummary({
        processed: response.processed,
        predicted: response.predicted,
        notFound: response.not_found,
        failed: response.failed
      });
      setBatchResults(response.results || []);
      if (onBatchResults) onBatchResults(response.results || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <div className="page-panel">
      <div className="card shadow-sm border-0 mb-3">
        <div className="card-header bg-white border-0 py-3">
          <h5 className="mb-0">VCF Upload Lab</h5>
        </div>
        <div className="card-body">
          <p className="text-secondary mb-3">
            Upload a clinical `.vcf` file, preview parsed variants, then send one directly to Predict page.
            Sample file: <code>data/examples/example_variants.vcf</code>.
          </p>
          <div className="row g-2">
            <div className="col-md-8">
              <input
                className="form-control"
                type="file"
                accept=".vcf,.vcf.gz"
                onChange={(e) => setVcfFile(e.target.files?.[0] || null)}
              />
            </div>
            <div className="col-md-2">
              <label className="form-label mb-1 small text-muted">Max records</label>
              <input
                className="form-control"
                type="number"
                min="1"
                max="5000"
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Math.min(5000, Number(e.target.value) || 1)))}
              />
            </div>
            <div className="col-md-2">
              <label className="form-label mb-1 small text-muted">Parse file</label>
              <button className="btn btn-primary w-100" onClick={handleUpload} disabled={loading}>
                {loading ? "Parsing..." : "Parse VCF"}
              </button>
            </div>
            <div className="col-md-12">
              <p className="small text-secondary mb-2">
                The number above sets how many VCF variants are parsed and sent to batch prediction.
              </p>
              <button className="btn btn-success w-100" onClick={handleBatchPredict} disabled={batchLoading || !records.length}>
                {batchLoading ? "Running Batch Prediction..." : "Run Batch Prediction"}
              </button>
            </div>
          </div>
          {error && <div className="alert alert-danger py-2 mt-3 mb-0">{error}</div>}
          {batchSummary && (
            <div className="alert alert-info py-2 mt-3 mb-0">
              Processed: {batchSummary.processed} | Predicted: {batchSummary.predicted} | Not Found: {batchSummary.notFound} | Failed: {batchSummary.failed}
            </div>
          )}
        </div>
      </div>

      <div className="card shadow-sm border-0">
        <div className="card-header bg-white border-0 py-3 d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Parsed Variants</h5>
          <span className="badge text-bg-light">{records.length}</span>
        </div>
        <div className="table-responsive">
          <table className="table table-striped table-hover mb-0 align-middle">
            <thead className="table-light">
              <tr>
                <th>Chrom</th>
                <th>Pos</th>
                <th>REF</th>
                <th>ALT</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan="5" className="text-center text-secondary py-4">
                    No parsed records yet.
                  </td>
                </tr>
              ) : (
                records.map((row, idx) => (
                  <tr key={`${row.chrom}-${row.pos}-${row.ref}-${row.alt}-${idx}`}>
                    <td>{row.chrom}</td>
                    <td>{row.pos}</td>
                    <td>{row.ref}</td>
                    <td>{row.alt}</td>
                    <td>
                      <button className="btn btn-sm btn-outline-success" onClick={() => onSelectVariant(row)}>
                        Use in Predict
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {batchResults.length > 0 && (
      <div className="card shadow-sm border-0 mt-3">
        <div className="card-header bg-white border-0 py-3">
          <div className="d-flex justify-content-between align-items-center">
            <h5 className="mb-0">Batch Prediction Results</h5>
            <button
              className="btn btn-sm btn-outline-primary"
              onClick={() => exportBatchReportCSV(batchSummary, batchResults)}
              disabled={!batchResults.length}
            >
              Download Report
            </button>
          </div>
        </div>
          <div className="table-responsive">
            <table className="table table-striped table-hover mb-0 align-middle">
              <thead className="table-light">
                <tr>
                  <th>Variant</th>
                  <th>Status</th>
                  <th>Prediction</th>
                  <th>Probability</th>
                  <th>Confidence</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {batchResults.map((row, idx) => (
                  <tr key={`${row.chrom}-${row.pos}-${row.ref}-${row.alt}-batch-${idx}`}>
                    <td>{row.chrom}:{row.pos} {row.ref}&gt;{row.alt}</td>
                    <td>{row.status}</td>
                    <td>{row.label || "N/A"}</td>
                    <td>{row.probability !== null && row.probability !== undefined ? `${(row.probability * 100).toFixed(2)}%` : "N/A"}</td>
                    <td>{row.confidence_score !== null && row.confidence_score !== undefined ? `${(row.confidence_score * 100).toFixed(2)}%` : "N/A"}</td>
                    <td>{row.message || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toFixed(digits);
}

function PageMonitoring({ summary, events, loading, onRefresh }) {
  const latestEvents = events?.items || [];
  const grafanaUrl = `${window.location.protocol}//${window.location.hostname}:3001`;
  const prometheusUrl = `${window.location.protocol}//${window.location.hostname}:9090`;
  const metricsUrl = `${window.location.protocol}//${window.location.hostname}:8000/metrics`;

  return (
    <div className="page-panel">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h4 className="mb-1">Runtime Monitoring</h4>
          <p className="text-secondary mb-0">Live model-serving health, prediction behavior, and recent event logs.</p>
        </div>
        <button className="btn btn-outline-primary" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Logged Events</h6>
              <h2 className="mb-0">{summary?.total_predictions ?? 0}</h2>
            </div>
          </div>
        </div>
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Pathogenic Rate</h6>
              <h2 className="mb-0">{formatPercent(summary?.pathogenic_rate)}</h2>
            </div>
          </div>
        </div>
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Avg Confidence</h6>
              <h2 className="mb-0">{formatPercent(summary?.average_confidence)}</h2>
            </div>
          </div>
        </div>
        <div className="col-xl-3 col-md-6">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-body">
              <h6 className="text-secondary">Avg Latency</h6>
              <h2 className="mb-0">{formatNumber(summary?.average_latency_ms, 1)} ms</h2>
            </div>
          </div>
        </div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-xl-4">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">Model Service</h5>
            </div>
            <div className="card-body">
              <p className="mb-2"><span className="fw-semibold">API:</span> {summary?.api_status || "unknown"}</p>
              <p className="mb-2"><span className="fw-semibold">Model:</span> {summary?.model_status || "unknown"}</p>
              <p className="mb-2"><span className="fw-semibold">Failures:</span> {summary?.failed_predictions ?? 0}</p>
              <p className="mb-0"><span className="fw-semibold">Low Confidence:</span> {summary?.low_confidence_predictions ?? 0}</p>
            </div>
          </div>
        </div>
        <div className="col-xl-4">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">Prediction Sources</h5>
            </div>
            <div className="card-body">
              {Object.entries(summary?.by_source || {}).length === 0 ? (
                <p className="text-secondary mb-0">No events yet.</p>
              ) : (
                Object.entries(summary.by_source).map(([source, count]) => (
                  <div key={source} className="d-flex justify-content-between mb-2">
                    <span>{source}</span>
                    <span className="badge text-bg-light">{count}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
        <div className="col-xl-4">
          <div className="card shadow-sm border-0 h-100">
            <div className="card-header bg-white border-0 py-3">
              <h5 className="mb-0">Monitoring Tools</h5>
            </div>
            <div className="card-body d-grid gap-2">
              <a className="btn btn-outline-primary" href={grafanaUrl} target="_blank" rel="noreferrer">Open Grafana</a>
              <a className="btn btn-outline-secondary" href={prometheusUrl} target="_blank" rel="noreferrer">Open Prometheus</a>
              <a className="btn btn-outline-dark" href={metricsUrl} target="_blank" rel="noreferrer">View Raw Metrics</a>
            </div>
          </div>
        </div>
      </div>

      <div className="card shadow-sm border-0">
        <div className="card-header bg-white border-0 py-3 d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Recent Monitoring Events</h5>
          <span className="badge text-bg-light">{latestEvents.length}</span>
        </div>
        <div className="table-responsive">
          <table className="table table-striped table-hover mb-0 align-middle">
            <thead className="table-light">
              <tr>
                <th>Time</th>
                <th>Endpoint</th>
                <th>Variant</th>
                <th>Status</th>
                <th>Prediction</th>
                <th>Confidence</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {latestEvents.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center text-secondary py-4">No monitoring events yet.</td>
                </tr>
              ) : (
                latestEvents.map((row, idx) => (
                  <tr key={`${row.timestamp}-${idx}`}>
                    <td>{row.timestamp ? new Date(row.timestamp).toLocaleString() : "N/A"}</td>
                    <td>{row.endpoint || "unknown"}</td>
                    <td>{row.chrom && row.pos ? `${row.chrom}:${row.pos} ${row.ref || ""}>${row.alt || ""}` : "N/A"}</td>
                    <td>
                      <span className={`badge ${row.status === "success" ? "text-bg-success" : "text-bg-danger"}`}>
                        {row.status || "unknown"}
                      </span>
                    </td>
                    <td>{row.prediction === 1 ? "PATHOGENIC" : row.prediction === 0 ? "BENIGN" : "N/A"}</td>
                    <td>{formatPercent(row.confidence_score)}</td>
                    <td>{formatNumber(row.latency_ms, 1)} ms</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function App() {
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
  const [monitoringEvents, setMonitoringEvents] = useState({ items: [] });
  const [fetchedRow, setFetchedRow] = useState(null);
  const [lastPrediction, setLastPrediction] = useState(null);
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
  }, []);

  const loadMonitoring = async () => {
    setMonitoringLoading(true);
    try {
      const [summaryRes, eventsRes] = await Promise.all([
        getMonitoringSummary(),
        getMonitoringPredictions(50)
      ]);
      setMonitoringSummary(summaryRes);
      setMonitoringEvents(eventsRes);
    } catch (e) {
      setAppError(e.message);
    } finally {
      setMonitoringLoading(false);
    }
  };

  useEffect(() => {
    loadMonitoring();
  }, []);

  const dashboard = useMemo(() => {
    const total = history.length;
    const pathogenic = history.filter((row) => row.label === "PATHOGENIC").length;
    const pathogenicRate = total ? (pathogenic / total) * 100 : 0;
    const withProba = history.filter((row) => row.probability !== null && row.probability !== undefined);
    const avgProbability = withProba.length
      ? (withProba.reduce((acc, row) => acc + row.probability, 0) / withProba.length) * 100
      : 0;
    const byChromMap = {};
    for (const row of history) byChromMap[row.chrom] = (byChromMap[row.chrom] || 0) + 1;
    const byChrom = Object.entries(byChromMap).sort((a, b) => b[1] - a[1]).slice(0, 6);
    return { total, pathogenic, pathogenicRate, avgProbability, byChrom };
  }, [history]);

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
        confidence: response.confidence_score ?? 0.5
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
      confidence: row.confidence_score ?? 0.5
    }));
    setHistory((prev) => [...newHistory, ...prev].slice(0, 200));
    loadMonitoring();
  };

  const navItems = [
    ["overview", "Overview"],
    ["predict", "Predict"],
    ["vcf", "VCF Lab"],
    ["monitoring", "Monitoring"]
  ];

  return (
    <div className="bg-body-tertiary min-vh-100">
      <nav className="navbar navbar-expand-lg bg-dark navbar-dark shadow-sm">
        <div className="container-fluid px-4">
          <span className="navbar-brand mb-0 h1">GenoPredict Clinical UI</span>
          <span className="badge text-bg-light">API: {health?.api_status || "unknown"}</span>
        </div>
      </nav>

      <div className="container-fluid px-4 py-4">
        <ul className="nav nav-pills bg-white rounded-3 shadow-sm p-2 mb-3">
          {navItems.map(([key, label]) => (
            <li className="nav-item" key={key}>
              <button
                type="button"
                className={`nav-link ${page === key ? "active" : ""}`}
                onClick={() => setPage(key)}
              >
                {label}
              </button>
            </li>
          ))}
          <li className="ms-auto d-flex gap-2">
            <button className="btn btn-sm btn-outline-primary" onClick={() => exportHistoryCSV(history)}>
              Export History
            </button>
            <button className="btn btn-sm btn-outline-danger" onClick={() => setHistory([])}>
              Clear
            </button>
          </li>
        </ul>

        {appError && <div className="alert alert-danger">{appError}</div>}

        {page === "overview" && (
          <PageOverview health={health} modelInfo={modelInfo} history={history} dashboard={dashboard} />
        )}
        {page === "predict" && (
          <PagePredict
            form={form}
            setForm={setForm}
            lookupStatus={lookupStatus}
            lookupMessage={lookupMessage}
            lookupLoading={lookupLoading}
            predictLoading={predictLoading}
            fetchedRow={fetchedRow}
            lastPrediction={lastPrediction}
            onLookup={handleLookup}
            onPredict={handlePredict}
            onReset={handleReset}
          />
        )}
        {page === "vcf" && <PageVcf onSelectVariant={handleSelectVcfVariant} onBatchResults={handleBatchResults} />}
        {page === "monitoring" && (
          <PageMonitoring
            summary={monitoringSummary}
            events={monitoringEvents}
            loading={monitoringLoading}
            onRefresh={loadMonitoring}
          />
        )}
      </div>
    </div>
  );
}
