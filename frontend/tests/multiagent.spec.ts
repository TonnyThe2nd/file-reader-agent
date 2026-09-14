import { test, expect } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`consulta multiagente em ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/config", (route) =>
      route.fulfill({
        json: {
          auth_required: false,
          max_upload_bytes: 10485760,
          multiagent_enabled: true,
        },
      }),
    );
    await page.route("**/api/ready", (route) =>
      route.fulfill({
        json: { owner: "local", ollama_configured: true },
      }),
    );
    await page.route("**/api/ask", (route) => {
      expect(route.request().postDataBuffer()!.toString()).toContain(
        "multiagent",
      );
      return route.fulfill({
        json: {
          interaction_id: "agent-answer",
          question: "Qual o total?",
          answer: "O total e 42 [1].",
          document_id: "doc1",
          mode: "multiagent",
          sources: [],
          latency_ms: 100,
          model_used: "test",
          cache_hit: false,
          input_tokens: 30,
          output_tokens: 15,
        },
      });
    });
    await page.goto("/");
    await expect(page.locator("#mode")).toHaveValue("direct");
    await page.locator("input[type=file]").setInputFiles({
      name: "total.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("O total e 42."),
    });
    await page.locator("#mode").selectOption("multiagent");
    await page.locator("#question").fill("Qual o total?");
    await page.getByRole("button", { name: "Perguntar ao documento" }).click();
    await expect(page.locator(".answer-text")).toHaveText("O total e 42 [1].");
    await expect(
      page.getByText("Resposta produzida pelo fluxo multiagente"),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `test-results/multiagent-${width}.png`,
      fullPage: true,
    });
  });
}

test("oculta multiagente quando desabilitado", async ({ page }) => {
  await page.route("**/api/config", (route) =>
    route.fulfill({
      json: {
        auth_required: false,
        max_upload_bytes: 10485760,
        multiagent_enabled: false,
      },
    }),
  );
  await page.route("**/api/ready", (route) =>
    route.fulfill({
      json: { owner: "local", ollama_configured: true },
    }),
  );
  await page.goto("/");
  await expect(page.locator("#mode option")).toHaveCount(2);
  await expect(page.locator("#mode")).toHaveValue("direct");
});
