import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { DatePipe } from "@angular/common";
import { Api, Policy, AuditEvent, errorMessage } from "../core/api";

@Component({
  imports: [FormsModule, DatePipe],
  template: `
    <h1>Administracao e auditoria</h1>
    @if (error()) {
      <p class="alert" role="alert">{{ error() }}</p>
    }
    @if (saved()) {
      <p role="status">Politica salva.</p>
    }
    @for (user of users(); track user.owner) {
      <form class="card policy-form" (ngSubmit)="save(user)">
        <h2>{{ user.owner }}</h2>
        <label
          >Perfil<select name="role" [(ngModel)]="user.role">
            <option value="user">Usuario</option>
            <option value="manager">Gestor</option>
            <option value="admin">Administrador</option>
          </select></label
        >
        <label
          >Equipes (separadas por virgula)<input
            name="teams"
            [ngModel]="user.teams.join(', ')"
            (ngModelChange)="user.teams = teams($event)"
        /></label>
        <label
          >Consultas por dia<input
            type="number"
            name="queries"
            [(ngModel)]="user.daily_queries"
            min="0"
        /></label>
        <label
          >Tokens por dia<input
            type="number"
            name="tokens"
            [(ngModel)]="user.daily_tokens"
            min="0"
        /></label>
        <label
          >Armazenamento em bytes<input
            type="number"
            name="storage"
            [(ngModel)]="user.storage_bytes"
            min="0"
        /></label>
        <label
          >Retencao em dias (vazio para desativar)<input
            type="number"
            name="retention"
            [(ngModel)]="user.retention_days"
            min="1"
        /></label>
        <p>
          Ao salvar a retencao, o worker pode iniciar a exclusao dos dados
          vencidos. Revise o prazo antes de salvar.
        </p>
        <button class="primary" [disabled]="busy()">Salvar politica</button>
      </form>
    }
    <h2>Registro de atividades</h2>
    <p>Usuarios consultam suas atividades; administradores consultam todas.</p>
    @for (event of events(); track event.id) {
      <article class="card">
        <strong>{{ event.action }}</strong>
        <p>
          {{ event.owner }} ·
          {{ event.created_at | date: "dd/MM/yyyy HH:mm" }} ·
          {{ event.resource_id }}
        </p>
      </article>
    }
    <button
      class="secondary"
      [disabled]="busy() || !more"
      (click)="loadAudit()"
    >
      Carregar atividades
    </button>
  `,
})
export class AdminPage {
  private api = inject(Api);
  users = signal<Policy[]>([]);
  events = signal<AuditEvent[]>([]);
  busy = signal(false);
  error = signal("");
  saved = signal(false);
  more = true;
  constructor() {
    this.api.me().subscribe({
      next: (me) => {
        if (me.role === "admin")
          this.api.users().subscribe({
            next: (users) => this.users.set(users),
            error: (error) => this.error.set(errorMessage(error)),
          });
      },
      error: (error) => this.error.set(errorMessage(error)),
    });
    this.loadAudit();
  }
  teams(value: string) {
    return [
      ...new Set(
        value
          .split(",")
          .map((team) => team.trim())
          .filter(Boolean),
      ),
    ];
  }
  save(user: Policy) {
    this.busy.set(true);
    this.saved.set(false);
    this.error.set("");
    this.api.savePolicy(user).subscribe({
      next: () => {
        this.busy.set(false);
        this.saved.set(true);
      },
      error: (error) => {
        this.busy.set(false);
        this.error.set(errorMessage(error));
      },
    });
  }
  loadAudit() {
    this.api.audit(this.events().length).subscribe({
      next: (rows) => {
        this.events.update((events) => [...events, ...rows]);
        this.more = rows.length === 100;
      },
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
}
