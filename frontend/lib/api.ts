/**
 * Typed API client for the Code Intelligence Platform backend.
 * All API calls go through this module — easy to swap base URL for prod.
 */
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
});

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description: string | null;
  source_type: "git_url" | "zip";
  source_url: string | null;
  status: "pending" | "parsing" | "analyzing" | "indexing" | "complete" | "failed";
  total_files: number;
  total_lines: number;
  created_at: string;
  updated_at: string;
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  status: string;
  progress: number;
  error: string | null;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface SourceFile {
  id: string;
  path: string;
  language: string;
  size_bytes: number;
  line_count: number;
  is_parsed: boolean;
  is_indexed: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface SearchResult {
  id: string;
  score: number;
  type: string;
  name: string;
  file_path: string;
  language: string;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  sources: Array<{ name: string; file: string; type: string; language: string; snippet: string }>;
  graph_context: unknown[];
}

// ── API functions ─────────────────────────────────────────────────────────────

export const projectsApi = {
  list: () => api.get<{ projects: Project[]; total: number }>("/projects"),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  uploadGit: (name: string, git_url: string, description?: string) =>
    api.post("/projects/upload/git", { name, git_url, description }),
  uploadZip: (name: string, file: File, description?: string) => {
    const form = new FormData();
    form.append("name", name);
    form.append("file", file);
    if (description) form.append("description", description);
    return api.post("/projects/upload/zip", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  delete: (id: string) => api.delete(`/projects/${id}`),
  files: (id: string) =>
    api.get<{ files: SourceFile[]; total: number; languages: Record<string, number> }>(
      `/projects/${id}/files`
    ),
  runs: (id: string) => api.get<AnalysisRun[]>(`/projects/${id}/runs`),
};

export const graphApi = {
  get: (projectId: string, nodeTypes?: string[]) =>
    api.get<{ nodes: GraphNode[]; edges: GraphEdge[]; total_nodes: number; total_edges: number }>(
      `/projects/${projectId}/graph`,
      { params: { node_types: nodeTypes } }
    ),
  neighbours: (projectId: string, nodeId: string) =>
    api.get(`/projects/${projectId}/graph/neighbours/${nodeId}`),
};

export const searchApi = {
  query: (projectId: string, q: string, language?: string) =>
    api.get<SearchResult[]>(`/projects/${projectId}/search`, {
      params: { q, language },
    }),
};

export const chatApi = {
  send: (projectId: string, message: string, history: Array<{ role: string; content: string }>) =>
    api.post<ChatResponse>(`/projects/${projectId}/chat`, { message, history }),
};

export const docsApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/docs`),
  diagram: (projectId: string, type: string) =>
    api.get(`/projects/${projectId}/diagrams/${type}`),
};

export const analysisApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/analysis`),
};
