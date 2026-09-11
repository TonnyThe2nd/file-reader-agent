import { Routes } from "@angular/router";
export const routes: Routes = [
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
