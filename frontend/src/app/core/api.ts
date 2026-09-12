import { Injectable, inject } from "@angular/core";
import {
  HttpClient,
  HttpErrorResponse,
  HttpInterceptorFn,
} from "@angular/common/http";
export interface Source {
  document_id?: string;
  page?: number;
  content: string;
  source: string;
  section?: string;
  score?: number;
}
export interface Answer {
  conversation_id?: string;
  interaction_id: string;
  answer: string;
  model_used: string;
  latency_ms: number;
  created_at: string | null;
  sources: Source[];
  cache_hit: boolean;
  document_id: string;
  mode: string;
  input_tokens: number;
  output_tokens: number;
}
export interface Interaction {
  id: string;
  question: string;
  answer: string;
  model_used: string;
  latency_ms: number;
  created_at: string;
  rating: number | null;
}
export interface InteractionDetail extends Interaction {
  document_id?: string;
  conversation_id?: string;
  sources: Source[];
  cache_hit: boolean;
  mode: string;
  input_tokens: number;
  output_tokens: number;
  comment: string | null;
}
export interface DocumentItem {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
}
export interface ChatMessage extends Answer {
  question: string;
  rating?: number | null;
  turn_number?: number;
}
export interface ConversationItem {
  id: string;
  title: string;
  document_id: string | null;
  created_at: string;
}
export interface ConversationDetail extends ConversationItem {
  messages: ChatMessage[];
  next_before: number | null;
}
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const token = sessionStorage.getItem("documento-token");
  return next(
    token && request.url.startsWith("/api/")
      ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : request,
  );
};
export interface Stats {
  total_interactions: number;
  total_feedbacks: number;
  positive_feedbacks: number;
  negative_feedbacks: number;
  positive_rate: number;
  avg_latency_ms: number;
  avg_latency_ms_last_24h: number;
}
@Injectable({ providedIn: "root" })
export class Api {
  private http = inject(HttpClient);
  health() {
    return this.http.get("/api/health");
  }
  config() {
    return this.http.get<{ auth_required: boolean; max_upload_bytes: number }>(
      "/api/config",
    );
  }
  ready() {
    return this.http.get<{ ollama_configured: boolean; owner: string }>(
      "/api/ready",
    );
  }
  ask(
    question: string,
    file: File | null,
    documentId = "",
    mode = "direct",
    useCache = true,
    conversationId = "",
    chat = false,
  ) {
    const body = new FormData();
    body.append("question", question);
    if (conversationId) body.append("conversation_id", conversationId);
    else if (file) body.append("file", file);
    else body.append("document_id", documentId);
    body.append("mode", mode);
    body.append("use_cache", String(useCache));
    body.append("chat", String(chat));
    return this.http.post<Answer>("/api/ask", body);
  }
  history(offset: number, search = "") {
    return this.http.get<Interaction[]>("/api/interactions", {
      params: { limit: 20, offset, search },
    });
  }
  detail(id: string) {
    return this.http.get<InteractionDetail>(`/api/interactions/${id}`);
  }
  conversations(offset = 0) {
    return this.http.get<ConversationItem[]>("/api/conversations", {
      params: { offset },
    });
  }
  conversation(id: string, before?: number) {
    return this.http.get<ConversationDetail>(`/api/conversations/${id}`, {
      params: before ? { before } : {},
    });
  }
  document(id: string) {
    return this.http.get<DocumentItem>(`/api/documents/${id}`);
  }
  documentContent(id: string) {
    return this.http.get(`/api/documents/${id}/content`, {
      responseType: "blob",
    });
  }
  deleteInteraction(id: string) {
    return this.http.delete(`/api/interactions/${id}`);
  }
  documents(offset = 0) {
    return this.http.get<DocumentItem[]>("/api/documents", {
      params: { limit: 20, offset },
    });
  }
  documentUpload(file: File) {
    const body = new FormData();
    body.append("file", file);
    return this.http.post<DocumentItem>("/api/documents", body);
  }
  deleteDocument(id: string) {
    return this.http.delete(`/api/documents/${id}`);
  }
  stats() {
    return this.http.get<Stats>("/api/stats");
  }
  feedback(id: string, rating: number, comment: string) {
    return this.http.post("/api/feedback", {
      interaction_id: id,
      rating,
      comment: comment || null,
    });
  }
}
export function errorMessage(error: HttpErrorResponse): string {
  if (error.status === 401)
    return "Sua chave de acesso é inválida. Saia e entre novamente.";
  if (error.status === 0 || error.status === 504)
    return "Não foi possível concluir a conexão. Verifique se a API está disponível e tente novamente.";
  const detail = error.error?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return "Verifique os campos enviados e tente novamente.";
  return "Não foi possível concluir a solicitação. Tente novamente.";
}
