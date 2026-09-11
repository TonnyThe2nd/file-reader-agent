import { Component, input } from "@angular/core";
import { RouterLink } from "@angular/router";
import { Source } from "../core/api";

@Component({
  selector: "app-sources",
  imports: [RouterLink],
  template: `
    @for (source of sources(); track $index) {
      <blockquote>
        @if (documentId()) {
          <a
            class="source-link"
            [routerLink]="['/documentos', documentId(), 'visualizar']"
            [queryParams]="{ interaction: interactionId(), source: $index }"
          >
            [{{ $index + 1 }}] {{ source.source }} · {{ source.section }} ↗
          </a>
        } @else {
          <strong
            >[{{ $index + 1 }}] {{ source.source }} ·
            {{ source.section }} (arquivo indisponível)</strong
          >
        }
        <p>{{ source.content }}</p>
      </blockquote>
    }
  `,
})
export class SourcesComponent {
  sources = input<Source[]>([]);
  documentId = input<string | null>();
  interactionId = input.required<string>();
}
