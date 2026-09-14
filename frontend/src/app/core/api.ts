import { Injectable, inject } from "@angular/core";
import { Observable } from "rxjs";
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
  follow_up_questions?: string[];
  turn_number?: number;
  document_ids?: string[];
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
  can_manage?: boolean;
  category?: string | null;
  processing_status?: string;
  processing_progress?: number;
  processing_error?: string | null;
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
  parent_conversation_id?: string | null;
  parent_turn?: number | null;
  id: string;
  title: string;
  document_id: string | null;
  created_at: string;
}
export interface ConversationDetail extends ConversationItem {
  document_ids?: string[];
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
export interface Policy {
  owner: string;
  role: "admin" | "user" | "manager";
  teams: string[];
  daily_queries: number;
  daily_tokens: number;
  storage_bytes: number;
  retention_days: number | null;
}
export interface Analytics {
  errors_last_24h: number;
  error_rate_last_24h: number;
  scope: string;
  sample_size: number;
  total_tokens: number;
  estimated_cost: number;
  p95_latency_ms: number;
  citation_validity_rate: number;
  daily_queries: number;
  daily_reserved_tokens: number;
  processing: Record<string, number>;
  documents: { id: string; name: string; queries: number }[];
}
export interface AuditEvent {
  id: string;
  owner: string;
  action: string;
  resource_id: string | null;
  created_at: string;
}
export interface Grant {
  id: string;
  kind: string;
  recipient: string;
}
@Injectable({ providedIn: "root" })
export class Api {
  private http = inject(HttpClient);
  me() {
    return this.http.get<Policy>("/api/me");
  }
  users() {
    return this.http.get<Policy[]>("/api/admin/users");
  }
  savePolicy(policy: Policy) {
    const { owner, ...body } = policy;
    return this.http.put<Policy>(
      `/api/admin/users/${encodeURIComponent(owner)}`,
      body,
    );
  }
  audit(offset = 0) {
    return this.http.get<AuditEvent[]>("/api/audit", { params: { offset } });
  }
  analytics(team = "") {
    return this.http.get<Analytics>("/api/analytics", {
      params: team ? { team } : {},
    });
  }
  grants(id: string) {
    return this.http.get<Grant[]>(`/api/documents/${id}/grants`);
  }
  share(id: string, kind: string, recipient: string) {
    return this.http.post<Grant>(`/api/documents/${id}/grants`, {
      kind,
      recipient,
    });
  }
  revoke(id: string, grant: string) {
    return this.http.delete(`/api/documents/${id}/grants/${grant}`);
  }
  health() {
    return this.http.get("/api/health");
  }
  config() {
    return this.http.get<{
      auth_required: boolean;
      max_upload_bytes: number;
      multiagent_enabled: boolean;
    }>("/api/config");
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
    documentIds: string[] = [],
    hybrid = true,
    rerank = true,
    onToken?: (token: string) => void,
  ) {
    const body = new FormData();
    body.append("question", question);
    if (conversationId) body.append("conversation_id", conversationId);
    else if (documentIds.length)
      documentIds.forEach((id) => body.append("document_ids", id));
    else if (file) body.append("file", file);
    else body.append("document_id", documentId);
    body.append("mode", mode);
    body.append("use_cache", String(useCache));
    body.append("chat", String(chat));
    body.append("hybrid", String(hybrid));
    body.append("rerank", String(rerank));
    if (onToken && mode !== "multiagent") {
      body.append("stream", "true");
      return new Observable<Answer>((subscriber) => {
        const controller = new AbortController();
        const token = sessionStorage.getItem("documento-token");
        void (async () => {
          try {
            const response = await fetch("/api/ask", {
              method: "POST",
              body,
              signal: controller.signal,
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!response.ok)
              throw new HttpErrorResponse({
                status: response.status,
                error: await response.json(),
              });
            const reader = response.body!.getReader();
            const decoder = new TextDecoder();
            let buffer = "",
              complete = false;
            while (!complete) {
              const chunk = await reader.read();
              if (chunk.done) break;
              buffer += decoder.decode(chunk.value, { stream: true });
              let end: number;
              while ((end = buffer.indexOf("\n\n")) >= 0) {
                const event = buffer.slice(0, end);
                buffer = buffer.slice(end + 2);
                const kind = event
                  .split("\n")
                  .find((line) => line.startsWith("event: "))
                  ?.slice(7);
                const raw = event
                  .split("\n")
                  .find((line) => line.startsWith("data: "))
                  ?.slice(6);
                if (!raw) continue;
                const value = JSON.parse(raw);
                if (kind === "token") onToken(value.text);
                if (kind === "error")
                  throw new HttpErrorResponse({
                    status: value.status || 500,
                    error: value,
                  });
                if (kind === "done") {
                  complete = true;
                  subscriber.next(value);
                  subscriber.complete();
                }
              }
            }
            if (!complete)
              throw new HttpErrorResponse({
                status: 502,
                error: { detail: "Resposta interrompida. Tente novamente." },
              });
          } catch (error) {
            if (!controller.signal.aborted) subscriber.error(error);
          }
        })();
        return () => controller.abort();
      });
    }
    return this.http.post<Answer>("/api/ask", body);
  }
  branch(conversationId: string, turn: number, documentIds?: string[]) {
    return this.http.post<{ id: string }>(
      `/api/conversations/${conversationId}/branches`,
      { turn, document_ids: documentIds },
    );
  }
  history(offset: number, search = "", filters: Record<string, string> = {}) {
    return this.http.get<Interaction[]>("/api/interactions", {
      params: { limit: 20, offset, search, ...filters },
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
  documents(offset = 0, filters: Record<string, string> = {}) {
    return this.http.get<DocumentItem[]>("/api/documents", {
      params: { limit: 20, offset, ...filters },
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
  retryDocument(id: string) {
    return this.http.post<DocumentItem>(`/api/documents/${id}/retry`, {});
  }
  categorizeDocument(id: string, category: string) {
    return this.http.patch<DocumentItem>(`/api/documents/${id}`, {
      category: category || null,
    });
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
