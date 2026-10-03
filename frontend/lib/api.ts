/**
 * API client for RootTrace backend.
 * Handles auth headers automatically.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("rt_token") || "";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (res.status === 401) {
    localStorage.removeItem("rt_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Incidents
  getIncidents: () => request<any[]>("/api/incidents"),
  getIncident: (id: string) => request<any>(`/api/incidents/${id}`),
  createIncident: (data: any) => request<any>("/api/incidents", { method: "POST", body: JSON.stringify(data) }),
  startInvestigation: (id: string) => request<any>(`/api/incidents/${id}/investigate`, { method: "POST" }),
  getEvents: (id: string) => request<any[]>(`/api/incidents/${id}/events`),
  getHypotheses: (id: string) => request<any[]>(`/api/incidents/${id}/hypotheses`),
  getEvidence: (id: string) => request<any[]>(`/api/incidents/${id}/evidence`),
  getRecommendations: (id: string) => request<any[]>(`/api/incidents/${id}/recommendations`),

  // Approvals
  approve: (recId: string, reason?: string) => request<any>(`/api/recommendations/${recId}/approve`, {
    method: "POST", body: JSON.stringify({ reason: reason || "" })
  }),
  reject: (recId: string, reason?: string) => request<any>(`/api/recommendations/${recId}/reject`, {
    method: "POST", body: JSON.stringify({ reason: reason || "" })
  }),

  // Evaluation
  getEvaluationResults: () => request<any>("/api/evaluation/results"),
};
