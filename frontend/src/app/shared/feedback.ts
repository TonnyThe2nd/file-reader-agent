import { Component, inject, input, output, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { finalize } from "rxjs";
import { Api, errorMessage } from "../core/api";

@Component({
  selector: "app-feedback",
  imports: [FormsModule],
  template: `@if (rating() || saved()) {
      <p role="status">
        {{
          saved()
            ? "Avaliação enviada. Obrigado!"
            : "Esta resposta já foi avaliada."
        }}
      </p>
    } @else {
      <div class="feedback">
        <label [for]="'feedback-' + interactionId()"
          >Comentário (opcional)</label
        >
        <textarea
          [id]="'feedback-' + interactionId()"
          [(ngModel)]="comment"
          maxlength="1000"
          rows="2"
          [disabled]="busy()"
        ></textarea>
        <div class="feedback-actions">
          <button class="secondary" [disabled]="busy()" (click)="rate(1)">
            + Útil
          </button>
          <button class="secondary" [disabled]="busy()" (click)="rate(-1)">
            − Não foi útil
          </button>
        </div>
        @if (error()) {
          <p role="alert">{{ error() }}</p>
        }
      </div>
    }`,
})
export class FeedbackComponent {
  private api = inject(Api);
  interactionId = input.required<string>();
  rating = input<number | null>(null);
  rated = output<number>();
  comment = "";
  busy = signal(false);
  saved = signal(false);
  error = signal("");

  rate(rating: number) {
    if (this.busy() || this.saved() || this.rating()) return;
    this.busy.set(true);
    this.error.set("");
    this.api
      .feedback(this.interactionId(), rating, this.comment.trim())
      .pipe(finalize(() => this.busy.set(false)))
      .subscribe({
        next: () => {
          this.saved.set(true);
          this.rated.emit(rating);
        },
        error: (error) => this.error.set(errorMessage(error)),
      });
  }
}
