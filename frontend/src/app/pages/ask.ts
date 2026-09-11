import { Component, inject, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { finalize } from "rxjs";
import { Api, Answer, errorMessage } from "../core/api";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { FeedbackComponent } from "../shared/feedback";
@Component({
  standalone: true,
  imports: [FormsModule, DecimalPipe, RouterLink, FeedbackComponent],
  templateUrl: "./ask.html",
})
export class AskPage {
  private api = inject(Api);
  question = "";
  file = signal<File | null>(null);
  busy = signal(false);
  error = signal("");
  answer = signal<Answer | null>(null);
  dragging = signal(false);
  documentId =
    inject(ActivatedRoute).snapshot.queryParamMap.get("document") || "";
  documentName =
    inject(ActivatedRoute).snapshot.queryParamMap.get("name") ||
    "Documento salvo";
  mode = "direct";
  useCache = true;
  maxBytes = 10485760;
  constructor() {
    this.api.config().subscribe({
      next: (config) => (this.maxBytes = config.max_upload_bytes),
      error: () => {},
    });
  }
  suggestions = [
    "Faça um resumo dos principais pontos.",
    "Quais são as informações mais importantes?",
    "Explique este documento de forma simples.",
  ];
  select(event: Event) {
    const input = event.target as HTMLInputElement;
    this.accept(input.files?.[0]);
    input.value = "";
  }
  drop(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(false);
    if (!this.busy()) this.accept(event.dataTransfer?.files[0]);
  }
  accept(file?: File) {
    if (!file) return;
    this.error.set("");
    if (!/\.(pdf|txt|md|csv|json|png|jpe?g|webp)$/i.test(file.name)) {
      this.error.set(
        "Formato não suportado. Selecione PDF, texto ou uma imagem PNG, JPEG ou WEBP.",
      );
      return;
    }
    if (!file.size || file.size > this.maxBytes) {
      this.error.set(
        `Selecione um arquivo com conteúdo, de até ${this.maxBytes / 1048576} MiB.`,
      );
      return;
    }
    this.documentId = "";
    this.file.set(file);
    this.answer.set(null);
  }
  send() {
    const file = this.file();
    if ((!file && !this.documentId) || !this.question.trim() || this.busy())
      return;
    this.busy.set(true);
    this.error.set("");
    this.answer.set(null);
    this.api
      .ask(
        this.question.trim(),
        file,
        this.documentId,
        this.mode,
        this.useCache,
      )
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: (answer) => this.answer.set(answer),
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
}
