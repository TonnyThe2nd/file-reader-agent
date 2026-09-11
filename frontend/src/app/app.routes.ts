import { Routes } from "@angular/router";
export const routes: Routes = [
  {
    path: "conversas",
    loadComponent: () =>
      import("./pages/conversations").then((m) => m.ConversationsPage),
  },
  {
    path: "documentos/:id/visualizar",
    loadComponent: () =>
      import("./pages/document-viewer").then((m) => m.DocumentViewerPage),
  },
  {
    path: "",
    loadComponent: () => import("./pages/ask").then((m) => m.AskPage),
  },
  {
    path: "historico",
    loadComponent: () => import("./pages/history").then((m) => m.HistoryPage),
  },
  {
    path: "historico/:id",
    loadComponent: () =>
      import("./pages/interaction-detail").then((m) => m.InteractionDetailPage),
  },
  {
    path: "documentos",
    loadComponent: () =>
      import("./pages/documents").then((m) => m.DocumentsPage),
  },
  {
    path: "estatisticas",
    loadComponent: () => import("./pages/stats").then((m) => m.StatsPage),
  },
  { path: "**", redirectTo: "" },
];
