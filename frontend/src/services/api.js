// Single place that knows how to talk to the FastAPI backend. Every component/hook goes
// through this file rather than calling fetch() directly, so the backend's actual contract
// (endpoints, request/response shapes) only has to be understood in one spot.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", token, json, formData, headers = {} } = {}) {
  const finalHeaders = { ...headers };
  if (token) finalHeaders.Authorization = `Bearer ${token}`;

  let body;
  if (json !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (formData !== undefined) {
    body = formData; // browser sets the multipart boundary itself - no Content-Type here
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers: finalHeaders, body });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new ApiError(data.detail || data.error || `Request failed (${res.status})`, res.status);
  }
  return data;
}

export async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.detail || "Login failed", res.status);
  return data.access_token;
}

export function createSession(token) {
  return request("/sessions", { method: "POST", token });
}

export function getSession(token, sessionId) {
  return request(`/sessions/${sessionId}`, { token });
}

export function resumeSession(token, sessionId) {
  return request(`/sessions/${sessionId}/resume`, { method: "POST", token });
}

export function submitAnswer(token, sessionId, fieldKey, text) {
  return request(`/sessions/${sessionId}/answer`, {
    method: "POST", token, json: { field_key: fieldKey, text },
  });
}

export function submitBatchAnswer(token, sessionId, text) {
  return request(`/sessions/${sessionId}/answer-batch`, { method: "POST", token, json: { text } });
}

export function correctField(token, sessionId, text) {
  return request(`/sessions/${sessionId}/correct`, { method: "PATCH", token, json: { text } });
}

export function confirmSession(token, sessionId) {
  return request(`/sessions/${sessionId}/confirm`, { method: "POST", token });
}

export async function transcribeAudio(token, blob) {
  const form = new FormData();
  const ext = (blob.type.split("/")[1] || "webm").split(";")[0];
  form.append("audio", blob, `recording.${ext}`);
  return request("/speech/transcribe", { method: "POST", token, formData: form });
}

export { ApiError };
