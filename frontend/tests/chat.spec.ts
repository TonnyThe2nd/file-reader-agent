import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: { auth_required: false, max_upload_bytes: 10485760 },
    }),
  );
  await page.route("**/api/ready", (route) =>
    route.fulfill({ json: { owner: "local", gemini_configured: true } }),
  );
});

test("continua e retoma conversa; nova conversa remove contexto", async ({
  page,
}) => {
  let count = 0;
  const message = {
    interaction_id: "m1",
    question: "Qual o prazo?",
    answer: "Cinco dias.",
    conversation_id: "chat1",
    document_id: "doc1",
    sources: [],
    latency_ms: 10,
    model_used: "test",
    cache_hit: false,
    mode: "direct",
  };
  await page.route("**/api/conversations/chat1", (route) =>
    route.fulfill({
      json: {
        id: "chat1",
        title: "Prazo",
        document_id: "doc1",
        messages: [message],
        next_before: null,
      },
    }),
  );
  await page.route("**/api/ask", (route) => {
    const body = route.request().postDataBuffer()!.toString();
    count++;
    if (count === 1) expect(body).toContain('name="file"');
    if (count === 2) {
      expect(body).toContain('name="conversation_id"');
      expect(body).toContain("chat1");
      expect(body).not.toContain('name="file"');
    }
    if (count === 3) {
      expect(body).not.toContain('name="conversation_id"');
      expect(body).toContain('name="document_id"');
    }
    return route.fulfill({
      json: {
        ...message,
        interaction_id: "m" + count,
        answer: count === 2 ? "O prazo começa amanhã." : "Cinco dias.",
      },
    });
  });
  await page.goto("/");
  await page.locator("input[type=file]").setInputFiles({
    name: "prazo.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Cinco dias."),
  });
  await page.getByLabel("O que você quer descobrir?").fill("Qual o prazo?");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page).toHaveURL(/conversation=chat1/);
  await page
    .getByLabel("O que você quer descobrir?")
    .fill("Quando começa esse prazo?");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.locator(".answer-text")).toHaveCount(2);
  await page.reload();
  await expect(page.locator(".answer-text")).toHaveText("Cinco dias.");
  await page
    .getByRole("button", { name: "Nova conversa", exact: true })
    .click();
  await expect(page.locator(".answer-text")).toHaveCount(0);
  await expect(page).not.toHaveURL(/conversation=/);
  await page.getByLabel("O que você quer descobrir?").fill("Outra pergunta");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.locator(".answer-text")).toHaveCount(1);
});

test("fonte abre texto autenticado e destaca trecho sem executar HTML", async ({
  page,
}) => {
  await page.route("**/api/interactions/m1", (route) =>
    route.fulfill({
      json: {
        id: "m1",
        question: "Prazo?",
        answer: "Cinco dias [1]",
        document_id: "doc1",
        sources: [
          {
            content: "Cinco dias.",
            source: "prazo.txt",
            section: "Texto, trecho 1",
          },
        ],
        rating: null,
        latency_ms: 10,
        model_used: "test",
        mode: "rag",
      },
    }),
  );
  await page.route("**/api/documents/doc1", (route) =>
    route.fulfill({
      json: { id: "doc1", name: "prazo.txt", mime_type: "text/plain" },
    }),
  );
  await page.route("**/api/documents/doc1/content", (route) =>
    route.fulfill({
      contentType: "text/plain",
      body: "<script>alert(1)</script>\nCinco dias.\nFim.",
    }),
  );
  await page.goto("/historico/m1");
  await page.getByRole("link", { name: /prazo.txt/ }).click();
  await expect(page.locator("mark")).toHaveText("Cinco dias.");
  await expect(page.locator(".document-text")).toContainText(
    "<script>alert(1)</script>",
  );
  await expect(page.locator(".document-text script")).toHaveCount(0);
});

test("fonte PDF aponta para a página e arquivo excluído informa erro", async ({
  page,
}) => {
  await page.route("**/api/interactions/m1", (route) =>
    route.fulfill({
      json: {
        id: "m1",
        document_id: "doc1",
        sources: [
          { content: "Trecho na segunda página.", source: "a.pdf", page: 2 },
        ],
        rating: null,
      },
    }),
  );
  await page.route("**/api/documents/doc1", (route) =>
    route.fulfill({
      json: { id: "doc1", name: "a.pdf", mime_type: "application/pdf" },
    }),
  );
  await page.route("**/api/documents/doc1/content", (route) =>
    route.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\n" }),
  );
  await page.goto("/documentos/doc1/visualizar?interaction=m1&source=0");
  await expect(page.locator("iframe")).toHaveAttribute("src", /#page=2$/);
  await expect(
    page.getByText("Trecho na segunda página.", { exact: true }),
  ).toBeVisible();
  await page.route("**/api/documents/doc1/content", (route) =>
    route.fulfill({
      status: 404,
      json: { detail: "Documento nao encontrado." },
    }),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "Documento não encontrado ou excluído",
  );
});
