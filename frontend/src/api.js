// All backend calls in one place. Paths go through the Vite proxy (/api -> backend).

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail);
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return body;
}

export const getTopics = (harder) => request(`/topics?harder=${harder}`);

export const createEssay = (topic, modifiers) =>
  request("/essays", { method: "POST", body: JSON.stringify({ topic, modifiers }) });

export const submitRevision = (essayId, text) =>
  request(`/essays/${essayId}/revisions`, { method: "POST", body: JSON.stringify({ text }) });

export const disputeIssue = (issueId, comment) =>
  request(`/issues/${issueId}/dispute`, { method: "POST", body: JSON.stringify({ comment }) });
