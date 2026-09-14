import { Component, DestroyRef, inject, signal } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { exportMarkdown, printAnswer } from "../shared/export";
import { DecimalPipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { finalize } from "rxjs";
import {
  Api,
  Answer,
  ChatMessage,
  DocumentItem,
  errorMessage,
} from "../core/api";
import { SourcesComponent } from "../shared/sources";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { FeedbackComponent } from "../shared/feedback";
@Component({
  standalone: true,
  imports: [
    FormsModule,
    DecimalPipe,
    RouterLink,
    FeedbackComponent,
    SourcesComponent,
  ],
  templateUrl: "./ask.html",
})
export class AskPage {
  private api = inject(Api);
  private destroyRef = inject(DestroyRef);
  streaming = false;
  partial = signal("");
  exportMarkdown = exportMarkdown;
  printAnswer = printAnswer;
  branchFrom(message: ChatMessage, replay = false) {
    if (!this.conversationId || !message.turn_number) return;
    this.busy.set(true);
    this.api
      .branch(
        this.conversationId,
        message.turn_number - (replay ? 1 : 0),
        this.selectedIds.length ? this.selectedIds : undefined,
      )
      .subscribe({
        next: (result) => {
          this.conversationId = result.id;
          this.question = replay ? message.question : "";
          this.loadConversation();
          void this.router.navigate([], {
            queryParams: { conversation: result.id },
            replaceUrl: true,
          });
        },
        error: (error) => {
          this.busy.set(false);
          this.error.set(errorMessage(error));
        },
      });
  }
  private router = inject(Router);
  question = "";
  file = signal<File | null>(null);
  busy = signal(false);
  error = signal("");
  answer = signal<Answer | null>(null);
  messages = signal<ChatMessage[]>([]);
  conversationId = "";
  chat = true;
  nextBefore: number | null = null;
  readOnly = false;
  dragging = signal(false);
  documentId =
    inject(ActivatedRoute).snapshot.queryParamMap.get("document") || "";
  documentName =
    inject(ActivatedRoute).snapshot.queryParamMap.get("name") ||
    "Documento salvo";
  mode = "direct";
  multiagentEnabled = signal(true);
  useCache = true;
  library = signal<DocumentItem[]>([]);
  selectedIds: string[] = [];
  hybrid = true;
  rerank = true;
  libraryOffset = 0;
  libraryMore = true;
  loadLibrary() {
    this.api.documents(this.libraryOffset).subscribe({
      next: (rows) => {
        this.library.update((current) => [...current, ...rows]);
        this.libraryOffset += rows.length;
        this.libraryMore = rows.length === 20;
      },
      error: (error) => this.error.set(errorMessage(error)),
    });
  }
  toggleDocument(id: string, checked: boolean) {
    this.selectedIds = checked
      ? [...this.selectedIds, id]
      : this.selectedIds.filter((value) => value !== id);
    this.file.set(null);
    this.mode = "rag";
  }
  maxBytes = 10485760;
  constructor() {
    const conversation =
      inject(ActivatedRoute).snapshot.queryParamMap.get("conversation");
    if (conversation) {
      this.conversationId = conversation;
      this.loadConversation();
    }
    this.api.config().subscribe({
      next: (config) => {
        this.maxBytes = config.max_upload_bytes;
        this.multiagentEnabled.set(config.multiagent_enabled === true);
      },
      error: () => {},
    });
  }
  loadConversation(older = false) {
    this.busy.set(true);
    this.error.set("");
    this.api
      .conversation(
        this.conversationId,
        older ? this.nextBefore || undefined : undefined,
      )
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: (result) => {
          this.messages.set(
            older ? [...result.messages, ...this.messages()] : result.messages,
          );
          this.documentId = result.document_id || "";
          this.selectedIds =
            result.document_ids && result.document_ids.length > 1
              ? result.document_ids
              : [];
          this.documentName = result.title;
          this.readOnly = !result.document_id;
          this.nextBefore = result.next_before;
          if (!older && result.messages.length)
            this.mode = result.messages[result.messages.length - 1].mode;
          if ((result.document_ids?.length || 0) > 1) this.mode = "rag";
        },
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
  newConversation() {
    this.conversationId = "";
    this.messages.set([]);
    this.answer.set(null);
    this.question = "";
    this.nextBefore = null;
    this.readOnly = false;
    this.error.set("");
    void this.router.navigate([], {
      queryParams: this.documentId
        ? { document: this.documentId, name: this.documentName }
        : {},
      replaceUrl: true,
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
    this.selectedIds = [];
    const pendingQuestion = this.question;
    this.newConversation();
    this.question = pendingQuestion;
    this.documentName = file.name;
    this.file.set(file);
    this.answer.set(null);
  }
  send() {
    const file = this.file();
    if (
      this.readOnly ||
      (!file &&
        !this.documentId &&
        !this.conversationId &&
        !this.selectedIds.length) ||
      !this.question.trim() ||
      this.busy()
    )
      return;
    this.busy.set(true);
    this.error.set("");
    this.answer.set(null);
    const question = this.question.trim();
    this.partial.set("");
    this.api
      .ask(
        this.question.trim(),
        file,
        this.documentId,
        this.mode,
        this.useCache,
        this.conversationId,
        this.chat,
        this.selectedIds,
        this.hybrid,
        this.rerank,
        this.streaming
          ? (token) => this.partial.update((value) => value + token)
          : undefined,
      )
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        finalize(() => this.busy.set(false)),
      )
      .subscribe({
        next: (answer) => {
          this.answer.set(answer);
          const message = { ...answer, question };
          this.messages.set(
            this.chat ? [...this.messages(), message] : [message],
          );
          this.conversationId = answer.conversation_id || "";
          if (this.conversationId)
            void this.router.navigate([], {
              queryParams: { conversation: this.conversationId },
              replaceUrl: true,
            });
          if (answer.document_id) {
            this.documentId = answer.document_id;
            this.file.set(null);
          }
          this.question = "";
        },
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
}
