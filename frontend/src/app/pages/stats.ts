import { Component, inject, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { finalize } from "rxjs";
import { Api, Stats, errorMessage } from "../core/api";
@Component({
  imports: [DecimalPipe],
  template: ` <div class="eyebrow">VISÃO GERAL</div>
    <h1>Conhecimento em <em>números.</em></h1>
    <p class="lead">Acompanhe o uso e a qualidade das interações salvas.</p>
    <div class="toolbar">
      <span>Dados do histórico</span
      ><button class="secondary" [disabled]="busy()" (click)="load()">
        ↻ Atualizar
      </button>
    </div>
    @if (error()) {
      <div class="alert" role="alert">{{ error() }}</div>
    }
    @if (busy()) {
      <div class="empty card" role="status">Carregando estatísticas…</div>
    }
    @if (data(); as stats) {
      <div class="stats-grid">
        <article class="card stat">
          <span>Interações</span><strong>{{ stats.total_interactions }}</strong
          ><small>Consultas registradas</small>
        </article>
        <article class="card stat">
          <span>Avaliações</span><strong>{{ stats.total_feedbacks }}</strong
          ><small>Feedbacks recebidos</small>
        </article>
        <article class="card stat highlight">
          <span>Aprovação</span
          ><strong>{{ stats.positive_rate | number: "1.0-1" }}<i>%</i></strong
          ><small>Entre as respostas avaliadas</small>
        </article>
      </div>
      <div class="stats-grid two">
        <article class="card stat">
          <h2>Qualidade das respostas</h2>
          <div class="rating-line">
            <span>Positivas</span><b>{{ stats.positive_feedbacks }}</b>
          </div>
          <div class="bar">
            <div [style.width.%]="stats.positive_rate"></div>
          </div>
          <div class="rating-line">
            <span>Negativas</span><b>{{ stats.negative_feedbacks }}</b>
          </div>
        </article>
        <article class="card stat">
          <h2>Tempo médio de resposta</h2>
          <div class="rating-line">
            <span>Todo o período</span
            ><b>{{ stats.avg_latency_ms / 1000 | number: "1.2-2" }} s</b>
          </div>
          <div class="rating-line">
            <span>Últimas 24 horas</span
            ><b
              >{{ stats.avg_latency_ms_last_24h / 1000 | number: "1.2-2" }} s</b
            >
          </div>
        </article>
      </div>
    }`,
})
export class StatsPage {
  private api = inject(Api);
  data = signal<Stats | null>(null);
  busy = signal(false);
  error = signal("");
  constructor() {
    this.load();
  }
  load() {
    this.busy.set(true);
    this.error.set("");
    this.data.set(null);
    this.api
      .stats()
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: (data) => this.data.set(data),
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
}
