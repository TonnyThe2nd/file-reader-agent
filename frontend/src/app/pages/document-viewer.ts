import {
  Component,
  DestroyRef,
  inject,
  OnDestroy,
  signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { DomSanitizer, SafeResourceUrl } from "@angular/platform-browser";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { forkJoin } from "rxjs";
import { Api, errorMessage } from "../core/api";

@Component({
  imports: [RouterLink],
  template: `
    <a class="secondary" routerLink="/documentos">← Biblioteca</a>
    @if (interactionId) {
      <a class="secondary" [routerLink]="['/historico', interactionId]"
        >Voltar à resposta</a
      >
    }
    <h1>{{ name() }}</h1>
    @if (error()) {
      <p class="alert" role="alert">{{ error() }}</p>
    }
    @if (loading()) {
      <p role="status">Abrindo documento…</p>
    }
    @if (excerpt()) {
      <section class="card response">
        <h2>Trecho citado {{ page() ? "· Página " + page() : "" }}</h2>
        <p class="answer-text">{{ excerpt() }}</p>
      </section>
    }
    @if (pdfUrl()) {
      <p>
        O visualizador abre na página da fonte. O trecho selecionado está
        exibido acima.
      </p>
      <iframe
        class="document-preview"
        title="Documento PDF"
        [src]="pdfUrl()"
      ></iframe>
    }
    @if (imageUrl()) {
      <img class="document-image" [src]="imageUrl()" alt="Documento original" />
    }
    @if (textReady()) {
      <pre
        class="card document-text">{{before()}}<mark id="selected-source">{{matched()}}</mark>{{after()}}</pre>
    }
  `,
})
export class DocumentViewerPage implements OnDestroy {
  private api = inject(Api);
  private destroyRef = inject(DestroyRef);
  private sanitizer = inject(DomSanitizer);
  private route = inject(ActivatedRoute);
  private blobUrl = "";
  interactionId = this.route.snapshot.queryParamMap.get("interaction") || "";
  name = signal("Documento");
  error = signal("");
  loading = signal(true);
  excerpt = signal("");
  page = signal<number | null>(null);
  pdfUrl = signal<SafeResourceUrl | null>(null);
  imageUrl = signal("");
  before = signal("");
  matched = signal("");
  after = signal("");
  textReady = signal(false);
  constructor() {
    const id = this.route.snapshot.paramMap.get("id")!;
    const sourceIndex = Number(
      this.route.snapshot.queryParamMap.get("source") || 0,
    );
    const open = () =>
      forkJoin({
        metadata: this.api.document(id),
        content: this.api.documentContent(id),
      })
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: async ({ metadata, content }) => {
            this.name.set(metadata.name);
            if (metadata.mime_type === "text/plain") {
              const text = await content.text();
              if (this.destroyRef.destroyed) return;
              const index = this.excerpt() ? text.indexOf(this.excerpt()) : -1;
              this.before.set(index < 0 ? text : text.slice(0, index));
              this.matched.set(index < 0 ? "" : this.excerpt());
              this.after.set(
                index < 0 ? "" : text.slice(index + this.excerpt().length),
              );
              this.textReady.set(true);
              if (index >= 0)
                setTimeout(() =>
                  document
                    .getElementById("selected-source")
                    ?.scrollIntoView({ block: "center" }),
                );
            } else {
              this.blobUrl = URL.createObjectURL(content);
              if (metadata.mime_type === "application/pdf")
                this.pdfUrl.set(
                  this.sanitizer.bypassSecurityTrustResourceUrl(
                    this.blobUrl + "#page=" + (this.page() || 1),
                  ),
                );
              else if (
                ["image/png", "image/jpeg", "image/webp"].includes(
                  metadata.mime_type,
                )
              )
                this.imageUrl.set(this.blobUrl);
            }
            this.loading.set(false);
          },
          error: (error) => {
            this.error.set(
              error.status === 404
                ? "Documento não encontrado ou excluído."
                : errorMessage(error),
            );
            this.loading.set(false);
          },
        });
    if (this.interactionId)
      this.api
        .detail(this.interactionId)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe({
          next: (item) => {
            if (item.document_id !== id) {
              this.error.set(
                "O documento desta fonte não está mais disponível.",
              );
              this.loading.set(false);
              return;
            }
            const source =
              Number.isInteger(sourceIndex) && sourceIndex >= 0
                ? item.sources[sourceIndex]
                : null;
            if (!source) {
              this.error.set("Fonte não encontrada.");
              this.loading.set(false);
              return;
            }
            this.excerpt.set(source.content);
            const legacyPage = Number(
              source.section?.match(/^Pagina (\d+)/)?.[1],
            );
            this.page.set(source.page || legacyPage || null);
            open();
          },
          error: (error) => {
            this.error.set(errorMessage(error));
            this.loading.set(false);
          },
        });
    else open();
  }
  ngOnDestroy() {
    if (this.blobUrl) URL.revokeObjectURL(this.blobUrl);
  }
}
