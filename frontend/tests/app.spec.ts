import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: { auth_required: false, max_upload_bytes: 10485760 },
    }),
  );
  await page.route("**/api/ready", (route) =>
    route.fulfill({ json: { gemini_configured: true, owner: "local" } }),
  );
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok" } }),
  );
});

test("envia arquivo e pergunta em multipart e exibe resposta segura", async ({
  page,
}) => {
  await page.route("**/api/ask", async (route) => {
    const request = route.request();
    expect(request.headers()["content-type"]).toContain("multipart/form-data");
    expect(request.postDataBuffer()?.toString()).toContain('name="question"');
    expect(request.postDataBuffer()?.toString()).toContain("O total e 42");
    await route.fulfill({
      json: {
        interaction_id: "abc",
        answer: "O total é 42. <script>alert(1)</script>",
        sources: [],
        latency_ms: 1500,
        model_used: "gemini-test",
        created_at: null,
      },
    });
  });
  await page.goto("/");
  await page.screenshot({ path: "test-results/consulta.png", fullPage: true });
  await expect(
    page.getByRole("button", { name: "Perguntar ao documento" }),
  ).toBeDisabled();
  await page.locator("input[type=file]").setInputFiles({
    name: "teste.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("O total e 42"),
  });
  await page.getByLabel("O que você quer descobrir?").fill("Qual o total?");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.locator(".answer-text")).toHaveText(
    "O total é 42. <script>alert(1)</script>",
  );
  await expect(page.locator(".answer-text script")).toHaveCount(0);
});

test("mostra erro do Gemini e permite tentar novamente", async ({ page }) => {
  await page.route("**/api/ask", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "O Gemini esta temporariamente indisponivel." },
    }),
  );
  await page.goto("/");
  await page.locator("input[type=file]").setInputFiles({
    name: "teste.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("texto"),
  });
  await page.getByLabel("O que você quer descobrir?").fill("Resuma o texto");
  await page.getByRole("button", { name: "Perguntar ao documento" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "temporariamente indisponivel",
  );
  await expect(
    page.getByRole("button", { name: "Perguntar ao documento" }),
  ).toBeEnabled();
});

test("histórico permite avaliar registros e navegar às estatísticas", async ({
  page,
}) => {
  await page.route("**/api/interactions*", (route) =>
    route.fulfill({
      json: [
        {
          id: "saved-id",
          question: "Pergunta salva",
          answer: "Resposta salva",
          created_at: "2026-09-11T12:00:00Z",
          latency_ms: 100,
          model_used: "test",
        },
      ],
    }),
  );
  await page.route("**/api/feedback", async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      interaction_id: "saved-id",
      rating: 1,
      comment: "Bom",
    });
    await route.fulfill({ json: { status: "ok" } });
  });
  await page.route("**/api/stats", (route) =>
    route.fulfill({
      json: {
        total_interactions: 3,
        total_feedbacks: 2,
        positive_feedbacks: 1,
        negative_feedbacks: 1,
        positive_rate: 50,
        avg_latency_ms: 1000,
        avg_latency_ms_last_24h: 2000,
      },
    }),
  );
  await page.goto("/historico");
  await expect(page.getByText("Pergunta salva")).toBeVisible();
  await page.getByRole("button", { name: "Avaliar resposta" }).click();
  await page.getByLabel("Comentário (opcional)").fill("Bom");
  await page.getByRole("button", { name: "+ Útil", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Avaliação enviada");
  await page.getByRole("link", { name: /Estatísticas/ }).click();
  await expect(page.getByText("50%", { exact: true })).toBeVisible();
});

test("layout móvel e falha de banco", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/interactions*", (route) =>
    route.fulfill({ status: 503, json: { detail: "Banco indisponivel" } }),
  );
  await page.goto("/");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("link", { name: /Histórico/ }).click();
  await expect(page.getByRole("alert")).toContainText("Banco indisponivel");
});
