import { Component, inject, signal } from "@angular/core";
import { DatePipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { finalize } from "rxjs";
import { RouterLink } from "@angular/router";
import { FeedbackComponent } from "../shared/feedback";
import { Api, Interaction, errorMessage } from "../core/api";
@Component({
  imports: [DatePipe, FormsModule, RouterLink, FeedbackComponent],
  template: ` <div class="eyebrow">SUA BIBLIOTECA DE CONSULTAS</div>
    <h1>Histórico de <em>interações.</em></h1>
    <p class="lead">Revisite as perguntas e avalie as respostas salvas.</p>
    <form class="search-form" (ngSubmit)="offset = 0; load()">
      <label for="search">Buscar pergunta</label
      ><input
        id="search"
        name="search"
        [(ngModel)]="search"
        maxlength="200"
      /><button class="secondary" [disabled]="busy()">Buscar</button>
    </form>
    <div class="toolbar">
      <span
        >{{ rows().length ? offset + 1 : 0 }}–{{ offset + rows().length }} ·
        Registros salvos</span
      ><button class="secondary" (click)="load()" [disabled]="busy()">
        ↻ Atualizar
      </button>
    </div>
    @if (error()) {
      <div class="alert" role="alert">{{ error() }}</div>
    }
    @if (busy()) {
      <div class="empty card" role="status">Carregando histórico…</div>
    } @else if (!rows().length && !error()) {
      <div class="empty card">
        <span>↗</span>
        <h2>Seu histórico começa aqui</h2>
        <p>
          Ainda não há interações salvas. Suas próximas consultas aparecerão
          aqui. Se usou a busca, tente outro termo.
        </p>
      </div>
    }
    @for (row of rows(); track row.id) {
      <article class="card history-item">
        <div class="history-meta">
          {{ row.created_at | date: "dd/MM/yyyy · HH:mm" }}
          <span>{{ row.model_used }}</span>
        </div>
        <h2>{{ row.question }}</h2>
        <p class="excerpt">{{ row.answer }}</p>
        <div class="feedback-actions">
          <a class="secondary" [routerLink]="['/historico', row.id]"
            >Ver resposta completa</a
          ><button
            class="secondary"
            [disabled]="busy()"
            (click)="remove(row.id)"
          >
            Excluir consulta
          </button>
        </div>
        @if (row.rating && selected() !== row.id) {
          <p>
            Resposta já avaliada:
            {{ row.rating === 1 ? "Útil" : "Não foi útil" }}
          </p>
        } @else {
          <button class="secondary" (click)="selected.set(row.id)">
            Avaliar resposta
          </button>
          @if (selected() === row.id) {
            <app-feedback
              [interactionId]="row.id"
              (rated)="rated(row.id, $event)"
            />
          }
        }
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
export class HistoryPage {
  private api = inject(Api);
  rows = signal<Interaction[]>([]);
  busy = signal(false);
  error = signal("");
  offset = 0;
  search = "";
  selected = signal("");
  constructor() {
    this.load();
  }
  load() {
    this.busy.set(true);
    this.error.set("");
    this.api
      .history(this.offset, this.search)
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: (rows) => this.rows.set(rows),
        error: (error) => {
          this.rows.set([]);
          this.error.set(errorMessage(error));
        },
      });
  }
  page(delta: number) {
    this.offset += delta;
    this.load();
  }
  rated(id: string, rating: number) {
    this.rows.update((rows) =>
      rows.map((row) => (row.id === id ? { ...row, rating } : row)),
    );
  }
  remove(id: string) {
    if (!confirm("Excluir esta consulta e sua avaliação?")) return;
    this.busy.set(true);
    this.error.set("");
    this.api.deleteInteraction(id).subscribe({
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
