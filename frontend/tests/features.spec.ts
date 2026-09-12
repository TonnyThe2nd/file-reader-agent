import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: { auth_required: false, max_upload_bytes: 10485760 },
    }),
  );
  await page.route("**/api/ready", (route) =>
    route.fulfill({ json: { owner: "local", ollama_configured: true } }),
  );
});

test("reutiliza documento salvo, seleciona RAG e avalia a resposta", async ({
  page,
}) => {
  await page.route("**/api/documents*", (route) =>
    route.fulfill({
      json: [
        {
          id: "doc-id",
          name: "Relatório.txt",
          mime_type: "text/plain",
          size_bytes: 30,
          created_at: "2026-09-11T12:00:00Z",
        },
      ],
    }),
  );
  await page.route("**/api/ask", async (route) => {
    const body = route.request().postDataBuffer()!.toString();
    expect(body).toContain('name="document_id"');
    expect(body).toContain("doc-id");
    expect(body).toContain("rag");
    expect(body).not.toContain('name="file"');
    await route.fulfill({
      json: {
        interaction_id: "interaction-id",
        answer: "O total é 42 [1].",
        sources: [
          {
            source: "Relatório.txt",
            section: "Texto, trecho 1",
            content: "O total é 42.",
          },
        ],
        cache_hit: true,
        latency_ms: 1,
        model_used: "test",
      },
    });
  });
  await page.route("**/api/feedback", (route) =>
    route.fulfill({ json: { status: "ok" } }),
  );
  await page.goto("/documentos");
  await page.getByRole("link", { name: "Perguntar", exact: true }).click();
  await page.getByLabel("Como consultar").selectOption("rag");
  await page.getByLabel("O que você quer descobrir?").fill("Qual o total?");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.locator("blockquote")).toContainText("O total é 42.");
  await expect(page.getByText(/Resposta reutilizada do cache/)).toBeVisible();
  await page.getByRole("button", { name: "+ Útil", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Avaliação enviada");
  await expect(
    page.getByRole("button", { name: "+ Útil", exact: true }),
  ).toHaveCount(0);
});

test("abre resposta completa e mostra avaliação anterior", async ({ page }) => {
  await page.route("**/api/interactions/record", (route) =>
    route.fulfill({
      json: {
        id: "record",
        question: "Minha pergunta",
        answer: "Resposta completa ".repeat(50),
        sources: [],
        rating: 1,
        comment: "Muito útil",
        created_at: "2026-09-11T12:00:00Z",
        model_used: "test",
        latency_ms: 100,
        mode: "direct",
        input_tokens: 20,
        output_tokens: 10,
      },
    }),
  );
  await page.goto("/historico/record");
  await expect(page.locator(".answer-text")).toHaveText(
    "Resposta completa ".repeat(50).trim(),
  );
  await expect(page.getByText("Seu comentário: Muito útil")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "+ Útil", exact: true }),
  ).toHaveCount(0);
});

test("login protege as telas e envia a chave somente para a API", async ({
  page,
}) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: { auth_required: true, max_upload_bytes: 10485760 },
    }),
  );
  await page.route("**/api/ready", (route) => {
    expect(route.request().headers()["authorization"]).toBe(
      "Bearer user-token",
    );
    return route.fulfill({ json: { owner: "ana", ollama_configured: true } });
  });
  await page.goto("/");
  await expect(page.getByLabel("O que você quer descobrir?")).toHaveCount(0);
  await page.getByLabel("Chave de acesso").fill("user-token");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.getByLabel("O que você quer descobrir?")).toBeVisible();
  await page.getByRole("button", { name: "Sair", exact: true }).click();
  await expect(page.getByLabel("Chave de acesso")).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("documento-token")),
  ).toBeNull();
});
