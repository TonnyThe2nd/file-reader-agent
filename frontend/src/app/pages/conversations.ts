import { Component, inject, signal } from "@angular/core";
import { RouterLink } from "@angular/router";
import { DatePipe } from "@angular/common";
import { Api, ConversationItem, errorMessage } from "../core/api";

@Component({
  imports: [RouterLink, DatePipe],
  template: `
    <h1>Suas <em>conversas.</em></h1>
    <p class="lead">Retome perguntas sobre seus documentos.</p>
    <a class="secondary" routerLink="/">Nova conversa</a>
    @if (error()) {
      <p class="alert" role="alert">{{ error() }}</p>
    }
    @if (busy()) {
      <p role="status">Carregando conversas…</p>
    }
    @for (row of rows(); track row.id) {
      <article class="card history-item">
        <h2>{{ row.title }}</h2>
        @if (row.parent_conversation_id) {
          <a
            class="secondary"
            routerLink="/"
            [queryParams]="{ conversation: row.parent_conversation_id }"
            >Conversa de origem · turno {{ row.parent_turn }}</a
          >
        }
        <p>{{ row.created_at | date: "dd/MM/yyyy HH:mm" }}</p>
        <a
          class="secondary"
          routerLink="/"
          [queryParams]="{ conversation: row.id }"
          >Abrir conversa</a
        >
        @if (!row.document_id) {
          <p>Documento excluído; mensagens disponíveis somente para leitura.</p>
        }
      </article>
    }
    @if (!busy() && !rows().length && !error()) {
      <p class="empty">Nenhuma conversa salva nesta página.</p>
    }
    <div class="pagination">
      <button
        class="secondary"
        [disabled]="busy() || !offset"
        (click)="page(-20)"
      >
        Anterior</button
      ><button
        class="secondary"
        [disabled]="busy() || rows().length < 20"
        (click)="page(20)"
      >
        Próxima
      </button>
    </div>
  `,
})
export class ConversationsPage {
  private api = inject(Api);
  rows = signal<ConversationItem[]>([]);
  error = signal("");
  busy = signal(false);
  offset = 0;
  constructor() {
    this.load();
  }
  page(delta: number) {
    this.offset += delta;
    this.load();
  }
  load() {
    this.busy.set(true);
    this.error.set("");
    this.api.conversations(this.offset).subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.busy.set(false);
      },
      error: (error) => {
        this.error.set(errorMessage(error));
        this.busy.set(false);
      },
    });
  }
}
