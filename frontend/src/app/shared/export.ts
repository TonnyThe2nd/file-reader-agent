import { Answer } from "../core/api";

type ExportableAnswer = Pick<Answer, "answer" | "sources"> & {
  question?: string;
};

export function exportMarkdown(result: ExportableAnswer) {
  const text =
    `# ${result.question || "Resposta"}\n\n${result.answer}\n\n## Fontes\n\n` +
    result.sources
      .map(
        (source, index) =>
          `### [${index + 1}] ${source.source} — ${source.section || ""}\n\n${source.content}`,
      )
      .join("\n\n");
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/markdown;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "resposta.md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function printAnswer(result: ExportableAnswer) {
  const frame = document.createElement("iframe");
  frame.style.display = "none";
  document.body.appendChild(frame);
  const target = frame.contentDocument!;
  const title = target.createElement("h1");
  title.textContent = result.question || "Resposta";
  target.body.appendChild(title);
  const text = target.createElement("pre");
  text.style.whiteSpace = "pre-wrap";
  text.style.fontFamily = "sans-serif";
  text.textContent =
    result.answer +
    "\n\nFontes\n" +
    result.sources
      .map((source, i) => `[${i + 1}] ${source.source}: ${source.content}`)
      .join("\n\n");
  target.body.appendChild(text);
  frame.contentWindow!.print();
  setTimeout(() => frame.remove(), 1000);
}
