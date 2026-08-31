import type {
  ChatRequest,
  ChatResponse,
  FileInfo,
  HealthResponse,
  ModelListResponse,
  Prompt,
  PromptListResponse,
  UploadResponse,
} from "./types";

const STORAGE_KEY = "ai-analysis.api-base";

export function getApiBase(): string {
  return localStorage.getItem(STORAGE_KEY) || "http://localhost:8000";
}

export function setApiBase(url: string): void {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/+$/, ""));
}

class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${getApiBase()}${path}`, init);
  } catch {
    throw new ApiError(`Нет связи с бэкендом (${getApiBase()}). Сервер запущен?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function listModels(): Promise<ModelListResponse> {
  return request<ModelListResponse>("/api/models");
}

export async function selectModel(model: string): Promise<void> {
  await request(`/api/models/select`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/upload", { method: "POST", body: form });
}

export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function streamChat(
  req: ChatRequest,
  onToken: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${getApiBase()}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new ApiError(`${res.status}: ${res.statusText}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const data = line.slice(5).trim();
      if (data === "[DONE]") return;
      onToken(data);
    }
  }
}

export async function listPrompts(): Promise<PromptListResponse> {
  return request<PromptListResponse>("/api/prompts");
}

export async function getSystemPrompt(): Promise<string> {
  const res = await request<{ content: string }>("/api/prompts/system");
  return res.content;
}

export async function updateSystemPrompt(content: string): Promise<void> {
  await request("/api/prompts/system", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function createPrompt(data: {
  name: string;
  content: string;
  description?: string;
}): Promise<Prompt> {
  return request<Prompt>("/api/prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deletePrompt(id: string): Promise<void> {
  await request(`/api/prompts/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function getTemplate(key: string): Promise<string> {
  const res = await request<{ content: string }>(`/api/prompts/templates/${key}`);
  return res.content;
}

export async function listCharts(): Promise<string[]> {
  const res = await request<{ charts: string[] }>("/api/charts");
  return res.charts;
}

export async function getChartHtml(id: string): Promise<string> {
  const res = await fetch(`${getApiBase()}/api/charts/${encodeURIComponent(id)}`);
  if (!res.ok) throw new ApiError(`${res.status}: не удалось загрузить график`);
  return res.text();
}

export async function deleteChart(id: string): Promise<void> {
  await request(`/api/charts/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export type { FileInfo };
