import { Component, inject, signal } from "@angular/core";
import { DatePipe, DecimalPipe } from "@angular/common";
import { RouterLink } from "@angular/router";
import { finalize } from "rxjs";
import { Api, DocumentItem, errorMessage } from "../core/api";

@Component({
  imports: [DatePipe, DecimalPipe, RouterLink],
  template: ` <div class="eyebrow">ARQUIVOS SALVOS</div>
    <h1>Sua biblioteca de <em>documentos.</em></h1>
    <p class="lead">
      Envie uma vez e faça novas perguntas sem reenviar o arquivo.
    </p>
    <label class="secondary"
      >Adicionar documento
      <input
        type="file"
        accept=".pdf,.txt,.md,.csv,.json,.png,.jpg,.jpeg,.webp"
        [disabled]="busy()"
        (change)="upload($event)"
    /></label>
    @if (error()) {
      <p class="alert" role="alert">{{ error() }}</p>
    }
    @if (busy()) {
      <p role="status">Carregando documentos…</p>
    }
    @if (!busy() && !rows().length && !error()) {
      <p class="empty card">
        Sua biblioteca está vazia. Envie seu primeiro documento.
      </p>
    }
    @for (row of rows(); track row.id) {
      <article class="card history-item">
        <h2>{{ row.name }}</h2>
        <p>
          {{ row.size_bytes / 1024 | number: "1.0-0" }} KB ·
          {{ row.created_at | date: "dd/MM/yyyy HH:mm" }}
        </p>
        <div class="feedback-actions">
          <a
            class="secondary"
            routerLink="/"
            [queryParams]="{ document: row.id, name: row.name }"
            >Perguntar</a
          >
          <button class="secondary" [disabled]="busy()" (click)="remove(row)">
            Excluir documento
          </button>
        </div>
      </article>
    }
    <div class="pagination">
      <button
        class="secondary"
        [disabled]="busy() || offset === 0"
        (click)="page(-20)"
      >
        ← Anterior</button
      ><button
        class="secondary"
        [disabled]="busy() || rows().length < 20"
        (click)="page(20)"
      >
        Próxima →
      </button>
    </div>`,
})
export class DocumentsPage {
  private api = inject(Api);
  rows = signal<DocumentItem[]>([]);
  busy = signal(false);
  error = signal("");
  offset = 0;
  constructor() {
    this.load();
  }
  load() {
    this.busy.set(true);
    this.error.set("");
    this.api
      .documents(this.offset)
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: (rows) => this.rows.set(rows),
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
  page(delta: number) {
    this.offset += delta;
    this.load();
  }
  upload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || this.busy()) return;
    this.busy.set(true);
    this.error.set("");
    this.api.documentUpload(file).subscribe({
      next: () => {
        this.offset = 0;
        this.load();
      },
      error: (error) => {
        this.error.set(errorMessage(error));
        this.busy.set(false);
      },
    });
  }
  remove(row: DocumentItem) {
    if (
      !confirm(
        `Excluir ${row.name}? O arquivo e o índice serão removidos. As consultas e seus trechos permanecerão no histórico.`,
      )
    )
      return;
    this.busy.set(true);
    this.error.set("");
    this.api.deleteDocument(row.id).subscribe({
      next: () => {
        if (this.rows().length === 1 && this.offset) this.offset -= 20;
        this.load();
      },
      error: (error) => {
        this.error.set(errorMessage(error));
        this.busy.set(false);
      },
    });
  }
}
