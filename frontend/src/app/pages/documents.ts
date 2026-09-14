import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormsModule } from "@angular/forms";
import { DatePipe, DecimalPipe } from "@angular/common";
import { RouterLink } from "@angular/router";
import { finalize, interval } from "rxjs";
import { Api, DocumentItem, Grant, errorMessage } from "../core/api";

@Component({
  imports: [DatePipe, DecimalPipe, RouterLink, FormsModule],
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
    <form (ngSubmit)="offset = 0; load()" class="toolbar">
      <label>Nome<input name="search" [(ngModel)]="search" /></label>
      <label>Categoria<input name="category" [(ngModel)]="category" /></label>
      <label
        >Tipo<select name="mime" [(ngModel)]="mime">
          <option value="">Todos</option>
          <option value="text/plain">Texto</option>
          <option value="application/pdf">PDF</option>
          <option value="image/png">PNG</option>
          <option value="image/jpeg">JPEG</option>
          <option value="image/webp">WEBP</option>
        </select></label
      >
      <label>Desde<input type="date" name="from" [(ngModel)]="from" /></label>
      <label>Ate<input type="date" name="to" [(ngModel)]="to" /></label>
      <button type="submit" class="secondary" [disabled]="busy()">
        Filtrar
      </button>
    </form>
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
        <p role="status">
          {{ statusLabel(row.processing_status) }} ·
          {{ row.processing_progress || 0 }}%
        </p>
        @if (row.processing_error) {
          <p>{{ row.processing_error }}</p>
        }
        @if (row.processing_status === "failed") {
          <button class="secondary" [disabled]="busy()" (click)="retry(row)">
            Tentar processamento novamente
          </button>
        }
        @if (row.can_manage !== false) {
          <label
            >Categoria<input
              #categoryInput
              [value]="row.category || ''"
              maxlength="100"
          /></label>
          <button
            class="secondary"
            [disabled]="busy()"
            (click)="categorize(row, categoryInput.value)"
          >
            Salvar categoria
          </button>
          @if (canShare()) {
            <button class="secondary" (click)="openSharing(row)">
              Compartilhar
            </button>
          }
        }
        @if (sharingId === row.id) {
          <section>
            <label
              >Destino<select [(ngModel)]="grantKind">
                <option value="user">Usuario</option>
                <option value="team">Equipe</option>
              </select></label
            >
            <label
              >Identificador<input [(ngModel)]="recipient" maxlength="100"
            /></label>
            <button
              class="secondary"
              [disabled]="busy() || !recipient.trim()"
              (click)="share()"
            >
              Conceder leitura
            </button>
            @for (grant of grants(); track grant.id) {
              <p>
                {{ grant.kind }}: {{ grant.recipient }}
                <button class="secondary" (click)="revoke(grant)">
                  Revogar
                </button>
              </p>
            }
          </section>
        }
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
          @if (row.can_manage !== false) {
            <button class="secondary" [disabled]="busy()" (click)="remove(row)">
              Excluir documento
            </button>
          }
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
  private destroyRef = inject(DestroyRef);
  canShare = signal(false);
  sharingId = "";
  grantKind = "team";
  recipient = "";
  grants = signal<Grant[]>([]);
  openSharing(row: DocumentItem) {
    this.sharingId = row.id;
    this.api.grants(row.id).subscribe({
      next: (grants) => this.grants.set(grants),
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  share() {
    this.api
      .share(this.sharingId, this.grantKind, this.recipient.trim())
      .subscribe({
        next: (grant) => {
          this.grants.update((rows) => [
            ...rows.filter((row) => row.id !== grant.id),
            grant,
          ]);
          this.recipient = "";
        },
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
  revoke(grant: Grant) {
    this.api.revoke(this.sharingId, grant.id).subscribe({
      next: () =>
        this.grants.update((rows) => rows.filter((row) => row.id !== grant.id)),
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  search = "";
  category = "";
  mime = "";
  from = "";
  to = "";
  filters() {
    const values: Record<string, string> = { search: this.search };
    if (this.category) values["category"] = this.category;
    if (this.mime) values["mime_type"] = this.mime;
    if (this.from) values["created_from"] = this.from + "T00:00:00Z";
    if (this.to) values["created_to"] = this.to + "T23:59:59.999999Z";
    return values;
  }
  statusLabel(status?: string) {
    return (
      (
        {
          pending: "Na fila",
          processing: "Processando",
          ready: "Pronto",
          failed: "Falha",
        } as Record<string, string>
      )[status || ""] || "Nao processado"
    );
  }
  retry(row: DocumentItem) {
    this.api.retryDocument(row.id).subscribe({
      next: () => this.load(),
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  categorize(row: DocumentItem, category: string) {
    this.api.categorizeDocument(row.id, category).subscribe({
      next: () => this.load(),
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  rows = signal<DocumentItem[]>([]);
  busy = signal(false);
  error = signal("");
  offset = 0;
  constructor() {
    this.api.me().subscribe({
      next: (me) => this.canShare.set(["admin", "manager"].includes(me.role)),
      error: () => {},
    });
    this.load();
    interval(5000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        if (
          !this.busy() &&
          this.rows().some((row) =>
            ["pending", "processing"].includes(row.processing_status || ""),
          )
        ) {
          this.api
            .documents(this.offset, this.filters())
            .pipe(takeUntilDestroyed(this.destroyRef))
            .subscribe({
              next: (rows) => this.rows.set(rows),
              error: () => {},
            });
        }
      });
  }
  load() {
    this.busy.set(true);
    this.error.set("");
    this.api
      .documents(this.offset, this.filters())
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
