const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  "";

async function parseResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }

  if (!response.ok) {
    const detail = formatApiError(payload?.detail || payload?.message || `HTTP ${response.status}`);
    throw new Error(detail);
  }
  return payload;
}

function formatApiError(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
        return field ? `${field}: ${item.msg}` : item.msg || JSON.stringify(item);
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.message || detail.msg || JSON.stringify(detail);
  }
  return String(detail);
}

export async function getHealth() {
  const response = await fetch(`${API_BASE}/api/health`);
  return parseResponse(response);
}

export async function getModelInfo() {
  const response = await fetch(`${API_BASE}/api/model-info`);
  return parseResponse(response);
}

export async function getMonitoringSummary() {
  const response = await fetch(`${API_BASE}/api/monitoring/summary`);
  return parseResponse(response);
}

export async function getMonitoringPredictions(limit = 25) {
  const response = await fetch(`${API_BASE}/api/monitoring/predictions?limit=${encodeURIComponent(limit)}`);
  return parseResponse(response);
}

export async function getMonitoringDrift() {
  const response = await fetch(`${API_BASE}/api/monitoring/drift`);
  return parseResponse(response);
}

export async function fetchFeatures({ chrom, pos, ref, alt }) {
  const params = new URLSearchParams({
    chrom: String(chrom),
    pos: String(pos),
    ref: String(ref),
    alt: String(alt)
  });
  const response = await fetch(`${API_BASE}/api/fetch-features?${params.toString()}`);
  return parseResponse(response);
}

export async function predictVariant(payload) {
  const response = await fetch(`${API_BASE}/api/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseResponse(response);
}

export async function uploadVcf(file, limit = 200) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/upload-vcf?limit=${encodeURIComponent(limit)}`, {
    method: "POST",
    body: formData
  });
  return parseResponse(response);
}

export async function predictVcfBatch(records, maxRecords = 200) {
  const response = await fetch(`${API_BASE}/api/vcf-batch-predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      records,
      max_records: maxRecords
    })
  });
  return parseResponse(response);
}
