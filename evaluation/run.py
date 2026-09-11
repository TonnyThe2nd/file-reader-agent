"""Avalia respostas gravadas; --api-url executa consultas reais e pode consumir cota."""

import argparse
import json
import os
from pathlib import Path

import httpx


def evaluate(dataset, predictions):
    indexed = {row["id"]: row for row in predictions}
    results = []
    for case in dataset:
        row = indexed.get(case["id"], {})
        answer = row.get("answer", "").casefold()
        sources = " ".join(s.get("content", "") for s in row.get("sources", [])).casefold()
        answer_ok = bool(answer) and all(
            term.casefold() in answer for term in case["expected_terms"]
        )
        source_ok = all(term.casefold() in sources for term in case["expected_source_terms"])
        results.append(
            {
                "id": case["id"],
                "answer_pass": answer_ok,
                "source_pass": source_ok,
                "latency_ms": row.get("latency_ms", 0),
            }
        )
    passed = sum(row["answer_pass"] and row["source_pass"] for row in results)
    return {
        "cases": results,
        "pass_rate": passed / len(results) if results else 0,
        "note": "Checagem por termos esperados; nao substitui revisao humana de fidelidade e completude.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="evaluation/dataset.json")
    parser.add_argument("--predictions", default="evaluation/predictions.example.json")
    parser.add_argument(
        "--api-url", help="URL da API sem /api no backend; usa consultas reais e grava historico"
    )
    parser.add_argument("--output", default="evaluation/report.json")
    args = parser.parse_args()
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if args.api_url:
        token = os.environ.get("EVALUATION_API_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        predictions = []
        with httpx.Client(
            base_url=args.api_url.rstrip("/") + "/", headers=headers, timeout=900
        ) as client:
            for case in dataset:
                response = client.post(
                    "ask",
                    data={"question": case["question"], "mode": "rag", "use_cache": "false"},
                    files={
                        "file": (
                            case["id"] + ".txt",
                            case["document"].encode("utf-8"),
                            "text/plain",
                        )
                    },
                )
                response.raise_for_status()
                predictions.append({"id": case["id"], **response.json()})
        Path(args.output).with_suffix(".predictions.json").write_text(
            json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        predictions = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    report = evaluate(dataset, predictions)
    report["mode"] = "live" if args.api_url else "recorded"
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{report['mode']}: {report['pass_rate']:.0%} — {args.output}")
    raise SystemExit(0 if report["pass_rate"] == 1 else 1)


if __name__ == "__main__":
    main()
