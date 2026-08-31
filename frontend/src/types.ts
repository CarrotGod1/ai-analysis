export interface ModelInfo {
  name: string;
  size: number;
  modified_at: string | null;
}

export interface ModelListResponse {
  models: ModelInfo[];
}

export interface FileInfo {
  filename: string;
  rows: number;
  columns: string[];
  dtypes: Record<string, string>;
  preview: Record<string, unknown>[];
  nulls: Record<string, number>;
  numeric_summary: Record<string, Record<string, number>> | null;
}

export interface UploadResponse {
  session_id: string;
  file_info: FileInfo;
}

export interface ChatRequest {
  message: string;
  model?: string | null;
  session_id?: string | null;
  system_prompt?: string | null;
}

export interface ChatResponse {
  reply: string;
  chart_path: string | null;
  model_used: string;
  tokens_used: number;
}

export interface Prompt {
  id: string;
  name: string;
  content: string;
  description: string;
}

export interface PromptListResponse {
  prompts: Prompt[];
}

export interface HealthResponse {
  status: string;
  ollama_connected: boolean;
  default_model: string;
}

export type ChatRole = "user" | "assistant" | "error";

export interface ChatEntry {
  role: ChatRole;
  content: string;
  model?: string;
  ts: number;
}
