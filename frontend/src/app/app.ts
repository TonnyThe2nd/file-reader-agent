import { Component, inject, signal } from "@angular/core";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { Api, errorMessage } from "./core/api";
import { FormsModule } from "@angular/forms";
@Component({
  selector: "app-root",
  imports: [RouterLink, RouterLinkActive, RouterOutlet, FormsModule],
  template: ` @if (!configured()) {
      <main>
        <p role="status">Carregando aplicação…</p>
        @if (error()) {
          <p role="alert">{{ error() }}</p>
          <button class="secondary" (click)="configure()">
            Tentar novamente
          </button>
        }
      </main>
    } @else if (authRequired() && !authenticated()) {
      <main class="login">
        <h1>Acesse seus <em>documentos.</em></h1>
        <p>Use a chave de acesso fornecida pelo administrador.</p>
        <form (ngSubmit)="login()">
          <label for="token">Chave de acesso</label
          ><input
            id="token"
            type="password"
            name="token"
            [(ngModel)]="token"
            required
            autocomplete="off"
          /><button class="primary" [disabled]="loggingIn() || !token.trim()">
            Entrar
          </button>
        </form>
        @if (error()) {
          <p role="alert">{{ error() }}</p>
        }
      </main>
    } @else {
      <div class="layout">
        <aside class="sidebar">
          <a routerLink="/" class="brand"
            ><span class="brand-icon">d.</span> documento<span class="brand-dot"
              >✦</span
            ></a
          >
          <div class="workspace-label">SEU ESPAÇO DE CONHECIMENTO</div>
          <nav aria-label="Navegação principal">
            <a
              routerLink="/"
              routerLinkActive="active"
              [routerLinkActiveOptions]="{ exact: true }"
              ><span>✦</span> Perguntar <small>01</small></a
            ><a routerLink="/historico" routerLinkActive="active"
              ><span>▤</span> Histórico <small>02</small></a
            ><a routerLink="/estatisticas" routerLinkActive="active"
              ><span>◴</span> Estatísticas <small>03</small></a
            ><a routerLink="/documentos" routerLinkActive="active"
              ><span>▧</span> Documentos <small>04</small></a
            >
          </nav>
          <div class="sidebar-note">
            <span class="note-symbol">↗</span
            ><strong>Dos arquivos às respostas.</strong>
            <p>Explore ideias, encontre detalhes e entenda seus documentos.</p>
          </div>
          <div class="connection">
            <span
              class="status-dot"
              [class.offline]="status() === 'API desconectada'"
            ></span
            >{{ status()
            }}<button
              class="icon-button"
              (click)="check()"
              aria-label="Verificar conexão"
            >
              ↻
            </button>
          </div>
        </aside>
        <div class="main">
          <header class="topbar">
            <span
              >Workspace <span class="slash">/</span>
              {{ owner() || "Meu espaço" }}</span
            >
            @if (authRequired()) {
              <button class="secondary" (click)="logout()">Sair</button>
            }
          </header>
          <main id="main"><router-outlet /></main>
          <footer>
            DOCUMENTO <span>Conhecimento, uma pergunta de cada vez.</span>
          </footer>
        </div>
      </div>
    }`,
})
export class App {
  private api = inject(Api);
  status = signal("Verificando API…");
  configured = signal(false);
  authRequired = signal(false);
  authenticated = signal(false);
  loggingIn = signal(false);
  error = signal("");
  owner = signal("");
  token = "";
  constructor() {
    this.configure();
  }
  configure() {
    this.error.set("");
    this.api.config().subscribe({
      next: (config) => {
        this.authRequired.set(config.auth_required);
        this.configured.set(true);
        if (!config.auth_required) this.check();
        else if (sessionStorage.getItem("documento-token"))
          this.validateSession();
      },
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  login() {
    sessionStorage.setItem("documento-token", this.token.trim());
    this.validateSession();
  }
  validateSession() {
    this.loggingIn.set(true);
    this.error.set("");
    this.api.ready().subscribe({
      next: (result) => {
        this.loggingIn.set(false);
        this.authenticated.set(true);
        this.owner.set(result.owner);
        this.token = "";
        this.status.set(
          result.gemini_configured ? "API conectada" : "Gemini não configurado",
        );
      },
      error: (error) => {
        this.loggingIn.set(false);
        sessionStorage.removeItem("documento-token");
        this.error.set(errorMessage(error));
      },
    });
  }
  logout() {
    sessionStorage.removeItem("documento-token");
    this.authenticated.set(false);
    this.owner.set("");
    this.token = "";
  }
  check() {
    this.status.set("Verificando API…");
    this.api.ready().subscribe({
      next: (result) => {
        this.owner.set(result.owner);
        this.status.set(
          result.gemini_configured ? "API conectada" : "Gemini não configurado",
        );
      },
      error: () => this.status.set("API desconectada"),
    });
  }
}
