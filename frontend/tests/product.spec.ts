import { test, expect } from "@playwright/test";

const documents = ["Receita.txt", "Despesa.txt"].map((name, index) => ({
  id: "doc-" + index,
  name,
  mime_type: "text/plain",
  size_bytes: 42,
  created_at: "2026-09-14T12:00:00Z",
  processing_status: "ready",
  processing_progress: 100,
}));
const answer = {
  interaction_id: "answer-id",
  answer: "Receita e despesa [1] [2].",
  document_id: "doc-0",
  document_ids: ["doc-0", "doc-1"],
  latency_ms: 10,
  mode: "rag",
  model_used: "local",
  sources: documents.map((document) => ({
    document_id: document.id,
    source: document.name,
    content: document.name,
    section: "Texto, trecho 1",
  })),
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: { auth_required: false, max_upload_bytes: 10485760 },
    }),
  );
  await page.route("**/api/ready", (route) =>
    route.fulfill({ json: { owner: "local", ollama_configured: true } }),
  );
  await page.route("**/api/documents?*", (route) =>
    route.fulfill({ json: documents }),
  );
});

test("multi-documento envia selecao e abre cada fonte no arquivo correto", async ({
  page,
}) => {
  await page.route("**/api/ask", (route) => {
    const body = route.request().postDataBuffer()!.toString();
    expect(body.match(/name="document_ids"/g)).toHaveLength(2);
    return route.fulfill({ json: answer });
  });
  await page.goto("/");
  await page.getByText("Consultar varios documentos", { exact: true }).click();
  await page.getByRole("button", { name: "Carregar documentos" }).click();
  await page.getByLabel("Receita.txt", { exact: true }).check();
  await page.getByLabel("Despesa.txt", { exact: true }).check();
  await page.getByLabel("O que você quer descobrir?").fill("Compare os totais");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.locator(".answer-text")).toHaveText(answer.answer);
  await expect(page.locator("blockquote a").nth(0)).toHaveAttribute(
    "href",
    /doc-0\/visualizar/,
  );
  await expect(page.locator("blockquote a").nth(1)).toHaveAttribute(
    "href",
    /doc-1\/visualizar/,
  );
});

test("streaming termina com resposta e permite exportacao", async ({
  page,
}) => {
  await page.route("**/api/ask", (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body:
        'event: token\ndata: {"text":"Receita"}\n\nevent: done\ndata: ' +
        JSON.stringify(answer) +
        "\n\n",
    }),
  );
  await page.goto("/?document=doc-0");
  await page.getByLabel("Mostrar resposta em tempo real").check();
  await page.getByLabel("O que você quer descobrir?").fill("Resumo");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.locator(".answer-text")).toHaveText(answer.answer);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar Markdown" }).click();
  expect((await download).suggestedFilename()).toBe("resposta.md");
});

test("comparacao exige dois documentos", async ({ page }) => {
  await page.route("**/api/ask", (route) => route.fulfill({ json: answer }));
  await page.goto("/comparar");
  await expect(
    page.getByRole("button", { name: "Comparar 0 documentos" }),
  ).toBeDisabled();
  await page.getByLabel("Receita.txt", { exact: true }).check();
  await page.getByLabel("Despesa.txt", { exact: true }).check();
  await page.getByRole("button", { name: "Comparar 2 documentos" }).click();
  await expect(page.locator(".answer-text")).toHaveText(answer.answer);
});
