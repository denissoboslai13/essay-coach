// All backend calls in one place. Paths go through the Vite proxy (/api -> backend) in development,
// and to the same server in production. The session is an httpOnly cookie the browser sends itself.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail);
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return body;
}

const post = (path, data) => request(path, { method: "POST", body: JSON.stringify(data) });

export const getAuthConfig = () => request("/auth/config");

export const getMe = () => request("/auth/me");

export const loginWithGoogle = (credential, inviteCode = null) =>
  post("/auth/google", { credential, invite_code: inviteCode });

export const logout = () => request("/auth/logout", { method: "POST" });

export const getTopics = (harder) => request(`/topics?harder=${harder}`);

export const createEssay = (topic, modifiers) => post("/essays", { topic, modifiers });

export const submitRevision = (essayId, text) => post(`/essays/${essayId}/revisions`, { text });

export const disputeIssue = (issueId, comment) => post(`/issues/${issueId}/dispute`, { comment });
