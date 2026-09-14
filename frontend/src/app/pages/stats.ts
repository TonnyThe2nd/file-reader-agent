import { Component, inject, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { finalize } from "rxjs";
import { Api, Stats, Analytics, errorMessage } from "../core/api";
@Component({
  imports: [DecimalPipe, FormsModule],
  template: ` <div class="eyebrow">VISÃO GERAL</div>
    <h1>Conhecimento em <em>números.</em></h1>
    <p class="lead">Acompanhe o uso e a qualidade das interações salvas.</p>
    <div class="toolbar">
      <span>Dados do histórico</span
      ><button class="secondary" [disabled]="busy()" (click)="load()">
        ↻ Atualizar
      </button>
    </div>
    <form (ngSubmit)="loadAnalytics()" class="toolbar">
      <label
        >Metricas de equipe (gestor)<input
          name="team"
          [(ngModel)]="team"
          placeholder="Vazio para meus dados" /></label
      ><button class="secondary">Consultar</button>
    </form>
    @if (analytics(); as metrics) {
      <section class="card">
        <h2>Uso e desempenho · {{ metrics.scope }}</h2>
        <p>
          Falhas nas ultimas 24h: {{ metrics.errors_last_24h }} ·
          {{ metrics.error_rate_last_24h | number: "1.1-1" }}% das consultas
        </p>
        <p>
          {{ metrics.total_tokens | number }} tokens · custo estimado
          {{ metrics.estimated_cost | number: "1.2-4" }}
        </p>
        <p>
          Consultas hoje: {{ metrics.daily_queries }} · tokens usados ou
          reservados: {{ metrics.daily_reserved_tokens | number }}
        </p>
        <p>
          Latencia p95: {{ metrics.p95_latency_ms / 1000 | number: "1.2-2" }} s
          · amostra: {{ metrics.sample_size }} consultas recentes
        </p>
        <p>
          Respostas RAG com referencias validas:
          {{ metrics.citation_validity_rate | number: "1.1-1" }}%. Este
          indicador verifica citacoes, nao a veracidade da resposta.
        </p>
        <h3>Uso por documento</h3>
        @for (document of metrics.documents; track document.id) {
          <p>{{ document.name }} · {{ document.queries }} consultas</p>
        }
      </section>
    }
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
  analytics = signal<Analytics | null>(null);
  team = "";
  loadAnalytics() {
    this.api.analytics(this.team.trim()).subscribe({
      next: (metrics) => this.analytics.set(metrics),
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  data = signal<Stats | null>(null);
  busy = signal(false);
  error = signal("");
  constructor() {
    this.load();
  }
  load() {
    this.api.analytics(this.team.trim()).subscribe({
      next: (metrics) => this.analytics.set(metrics),
      error: () => {},
    });
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
