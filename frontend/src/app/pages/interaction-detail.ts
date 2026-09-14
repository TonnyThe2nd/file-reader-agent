import { Component, inject, signal } from "@angular/core";
import { DatePipe, DecimalPipe } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { Api, InteractionDetail, errorMessage } from "../core/api";
import { FeedbackComponent } from "../shared/feedback";
import { SourcesComponent } from "../shared/sources";

@Component({
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    FeedbackComponent,
    SourcesComponent,
  ],
  template: ` <a class="secondary" routerLink="/historico"
      >← Voltar ao histórico</a
    >
    @if (error()) {
      <p class="alert" role="alert">{{ error() }}</p>
    }
    @if (row(); as item) {
      <section class="card response">
        <h1>{{ item.question }}</h1>
        <p>
          {{ item.created_at | date: "dd/MM/yyyy HH:mm" }} ·
          {{ item.model_used }} ·
          {{ item.latency_ms / 1000 | number: "1.1-1" }} s
        </p>
        <div class="answer-text">{{ item.answer }}</div>
        <app-sources
          [sources]="item.sources"
          [documentId]="item.document_id"
          [interactionId]="item.id"
        />
        @if (item.conversation_id) {
          <a
            class="secondary"
            routerLink="/"
            [queryParams]="{ conversation: item.conversation_id }"
            >Continuar conversa</a
          >
        }
        <p>
          {{
            item.mode === "multiagent"
              ? "Fluxo multiagente"
              : item.mode === "rag"
                ? "Busca por trechos"
                : "Consulta direta"
          }}
          · {{ item.cache_hit ? "Cache" : "Nova geração" }} · Tokens informados:
          {{ item.input_tokens }} entrada / {{ item.output_tokens }} saída
        </p>
        @if (item.comment) {
          <p>Seu comentário: {{ item.comment }}</p>
        }
        <app-feedback [interactionId]="item.id" [rating]="item.rating" />
      </section>
    } @else if (!error()) {
      <p role="status">Carregando consulta…</p>
    }`,
})
export class InteractionDetailPage {
  private api = inject(Api);
  row = signal<InteractionDetail | null>(null);
  error = signal("");
  constructor() {
    const id = inject(ActivatedRoute).snapshot.paramMap.get("id")!;
    this.api.detail(id).subscribe({
      next: (row) => this.row.set(row),
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
}
