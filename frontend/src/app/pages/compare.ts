import { Component, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { finalize } from "rxjs";
import { Api, Answer, DocumentItem, errorMessage } from "../core/api";
import { SourcesComponent } from "../shared/sources";
import { exportMarkdown, printAnswer } from "../shared/export";

@Component({
  imports: [FormsModule, SourcesComponent],
  template: `
    <h1>Comparar documentos</h1>
    <p>Selecione de 2 a 20 documentos e descreva o que deseja comparar.</p>
    <form (ngSubmit)="load(true)" class="toolbar">
      <label>Nome<input name="search" [(ngModel)]="search" /></label>
      <label>Categoria<input name="category" [(ngModel)]="category" /></label>
      <button class="secondary" [disabled]="busy()">Filtrar biblioteca</button>
    </form>
    @for (document of documents(); track document.id) {
      <label class="card document-choice"
        ><input
          type="checkbox"
          [checked]="selected.includes(document.id)"
          [disabled]="
            busy() || (selected.length >= 20 && !selected.includes(document.id))
          "
          (change)="toggle(document.id, $any($event.target).checked)"
        />{{ document.name }}</label
      >
    }
    @if (more) {
      <button class="secondary" (click)="load()" [disabled]="busy()">
        Carregar documentos
      </button>
    }
    <form (ngSubmit)="compare()">
      <label
        >Pergunta<textarea
          name="question"
          [(ngModel)]="question"
          maxlength="2000"
          required
        ></textarea>
      </label>
      <button
        class="primary"
        [disabled]="busy() || selected.length < 2 || !question.trim()"
      >
        Comparar {{ selected.length }} documentos
      </button>
    </form>
    @if (busy()) {
      <p role="status">Comparando documentos...</p>
    }
    @if (error()) {
      <p class="alert" role="alert">{{ error() }}</p>
    }
    @if (answer(); as result) {
      <section class="card response">
        <h2>Comparacao com fontes</h2>
        <div class="answer-text">{{ result.answer }}</div>
        <app-sources
          [sources]="result.sources"
          [interactionId]="result.interaction_id"
        />
        <button class="secondary" (click)="exportMarkdown(result)">
          Exportar Markdown
        </button>
        <button class="secondary" (click)="printAnswer(result)">
          Imprimir / salvar PDF
        </button>
      </section>
    }
  `,
})
export class ComparePage {
  private api = inject(Api);
  documents = signal<DocumentItem[]>([]);
  selected: string[] = [];
  search = "";
  category = "";
  question =
    "Compare os pontos em comum, as diferencas e as contradicoes. Cite as fontes e informe quando faltar evidencia.";
  answer = signal<Answer | null>(null);
  busy = signal(false);
  error = signal("");
  more = true;
  offset = 0;
  exportMarkdown = exportMarkdown;
  printAnswer = printAnswer;
  constructor() {
    this.load();
  }
  toggle(id: string, checked: boolean) {
    this.selected = checked
      ? [...this.selected, id]
      : this.selected.filter((value) => value !== id);
  }
  load(reset = false) {
    if (reset) {
      this.documents.set([]);
      this.selected = [];
      this.offset = 0;
    }
    const filters: Record<string, string> = { search: this.search };
    if (this.category) filters["category"] = this.category;
    this.api.documents(this.offset, filters).subscribe({
      next: (rows) => {
        this.documents.update((current) => [
          ...current,
          ...rows.filter((row) =>
            ["text/plain", "application/pdf"].includes(row.mime_type),
          ),
        ]);
        this.offset += rows.length;
        this.more = rows.length === 20;
      },
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  compare() {
    if (this.busy() || this.selected.length < 2) return;
    this.busy.set(true);
    this.error.set("");
    this.api
      .ask(this.question, null, "", "rag", true, "", false, this.selected)
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: (answer) => this.answer.set(answer),
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
}
