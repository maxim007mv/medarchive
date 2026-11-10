// k6 load test of TZ-backend DoD 4: p95 of GET /api/v1/documents < 300 ms with 1000 documents and
// 50 VU, no 5xx. Runs on the compose network (`make load`); setup() seeds one archive through the
// same path as the browser: uploads -> presigned POST to storage -> documents.
import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";

const API_URL = __ENV.API_URL;
const DOCUMENTS = Number(__ENV.LOAD_DOCUMENTS || 1000);
const POLICY_VERSION = "2026-11-10";
const SESSION_COOKIE = "__Host-ma_sid";
// Storage as seen from the compose network; the presigned policy is signed without the host.
const STORAGE_URL = "http://minio:9000";

const SOURCES = [
  ["01-general-blood-test.pdf", "Общий анализ крови", "analysis", "2026-04-08"],
  ["02-blood-biochemistry.pdf", "Биохимический анализ крови", "analysis", "2026-04-08"],
  ["03-lipid-profile.pdf", "Липидограмма", "analysis", "2026-05-21"],
  ["04-therapist-summary.pdf", "Заключение терапевта", "conclusion", "2026-04-10"],
  ["05-ultrasound-summary.pdf", "УЗИ почек и мочевого пузыря", "conclusion", "2026-05-22"],
  ["06-ecg-summary-undated.pdf", "ЭКГ покоя", "conclusion", null],
].map(([file, title, type, date]) => ({ file, title, type, date, bytes: open(`/fixtures/${file}`, "b") }));

const serverErrors = new Rate("server_errors");

export const options = {
  setupTimeout: "30m",
  scenarios: {
    list: { executor: "constant-vus", vus: 50, duration: "60s", exec: "list" },
  },
  thresholds: {
    "http_req_duration{name:documents.list}": ["p(95)<300"],
    "http_req_duration{name:documents.search}": ["p(95)<300"],
    server_errors: ["rate==0"],
    // A 429 is fast too: only 200 answers count towards the latency budget.
    checks: ["rate==1"],
  },
};

function uuid() {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (c ^ (Math.random() * 256) & (15 >> (c / 4))).toString(16),
  );
}

function expectStatus(response, status, what) {
  if (response.status !== status) {
    throw new Error(`${what}: ${response.status} request_id=${response.headers["X-Request-Id"]}`);
  }
  return response;
}

export function setup() {
  const created = expectStatus(
    http.post(
      `${API_URL}/api/v1/workspaces`,
      JSON.stringify({ consent: { policy_version: POLICY_VERSION, accepted: true } }),
      { headers: { "Content-Type": "application/json", "Idempotency-Key": uuid() } },
    ),
    201,
    "workspaces.create",
  );
  const session = created.cookies[SESSION_COOKIE][0].value;
  const auth = {
    "Content-Type": "application/json",
    Cookie: `${SESSION_COOKIE}=${session}`,
    "X-CSRF-Token": created.json("csrf_token"),
  };
  for (let n = 0; n < DOCUMENTS; n += 1) {
    const source = SOURCES[n % SOURCES.length];
    const upload = expectStatus(
      http.post(
        `${API_URL}/api/v1/uploads`,
        JSON.stringify({ original_name: source.file, size_bytes: source.bytes.byteLength, content_type: "application/pdf" }),
        { headers: { ...auth, "Idempotency-Key": uuid() } },
      ),
      201,
      "uploads.create",
    ).json();
    const storageUrl = upload.url.replace(/^https?:\/\/[^/]+/, STORAGE_URL);
    const form = { ...upload.fields, file: http.file(source.bytes, source.file, "application/pdf") };
    const stored = http.post(storageUrl, form);
    if (stored.status >= 300) throw new Error(`storage upload: ${stored.status}`);
    expectStatus(
      http.post(
        `${API_URL}/api/v1/documents`,
        JSON.stringify({ upload_id: upload.upload_id, title: source.title, type: source.type, document_date: source.date }),
        { headers: { ...auth, "Idempotency-Key": uuid() } },
      ),
      201,
      "documents.create",
    );
  }
  return { cookie: auth.Cookie };
}

export function list(data) {
  const params = { headers: { Cookie: data.cookie } };
  const page = http.get(`${API_URL}/api/v1/documents`, { ...params, tags: { name: "documents.list" } });
  const search = http.get(`${API_URL}/api/v1/documents?q=${encodeURIComponent("анализ")}`, {
    ...params,
    tags: { name: "documents.search" },
  });
  for (const response of [page, search]) {
    serverErrors.add(response.status >= 500);
    check(response, { "status 200": (r) => r.status === 200 });
  }
}
