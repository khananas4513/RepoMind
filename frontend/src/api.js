const BASE = "http://127.0.0.1:8000/api";

async function request(path, options) {
  const res = await fetch(BASE + path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const analyzeUrl = (url) => request("/analyze", json({ url }));

export const analyzeZip = (file) => {
  const form = new FormData();
  form.append("file", file);
  return request("/analyze/zip", { method: "POST", body: form });
};

export const getStatus = (id) => request(`/repos/${id}`);
export const getGraph = (id, includeTests) => request(`/repos/${id}/graph?include_tests=${includeTests}`);
export const getImpact = (id, path) => request(`/repos/${id}/impact?path=${encodeURIComponent(path)}`);
export const getFile = (id, path) => request(`/repos/${id}/file?path=${encodeURIComponent(path)}`);
export const askQuestion = (id, body) => request(`/repos/${id}/ask`, json(body));