import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.database import AsyncSessionFactory
from app.providers.factory import get_llm_provider
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.grounded import GroundedRAGEngine, INSUFFICIENT_EVIDENCE_MESSAGE, SOURCE_LABEL_PATTERN
from app.rag.retriever import SemanticRetriever


ACTIONABLE_PATTERN = re.compile(r"\b(should|can|step|try|focus|measure|start|use|build|test|define|remove)\b", re.IGNORECASE)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        dataset = json.load(handle)
    if not isinstance(dataset, list) or not dataset:
        raise ValueError("Evaluation dataset must be a non-empty JSON array.")
    for case in dataset:
        if not isinstance(case, dict) or not all(key in case for key in ("id", "user_question", "expected_topic", "expected_source", "expected_answer_characteristics")):
            raise ValueError("Every evaluation case must include the required fields.")
    return dataset


def source_text(source: Any) -> str:
    return " ".join(str(getattr(source, field, "") or "") for field in ("episode", "guest", "topic", "source_url")).casefold()


def cited_labels(answer: str) -> list[int]:
    return [int(match.group("index")) for match in SOURCE_LABEL_PATTERN.finditer(answer)]


def evaluate_case(case: dict[str, Any], response: Any) -> dict[str, Any]:
    sources = response.sources
    expected_source = case["expected_source"]
    expected_source_match = [index for index, source in enumerate(sources) if expected_source and expected_source.casefold() in source_text(source)]
    expected_topic = str(case["expected_topic"]).casefold()
    expected_topic_match = expected_topic == "out-of-domain" and not sources or any(expected_topic in source_text(source) for source in sources)
    rank = expected_source_match[0] + 1 if expected_source_match else None
    labels = cited_labels(response.answer)
    valid_citations = bool(labels) and all(1 <= label <= len(sources) for label in labels)
    characteristics = case["expected_answer_characteristics"]
    answer_lower = response.answer.casefold()
    expected_terms_present = all(term.casefold() in answer_lower for term in characteristics.get("expected_terms", []))
    actionable = bool(ACTIONABLE_PATTERN.search(response.answer))
    answer_relevance = expected_terms_present and (not characteristics.get("requires_actionable_language") or actionable)
    retrieval_relevance = (expected_source is None and not sources) or bool(expected_source_match)
    groundedness = (expected_source is None and response.answer == INSUFFICIENT_EVIDENCE_MESSAGE) or valid_citations
    citation_correctness = (expected_source is None and not labels) or (valid_citations and bool(set(labels) & {rank} if rank else False))
    out_of_domain = expected_source is None and not sources and response.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    return {
        "id": case["id"],
        "retrieved_sources": [source.model_dump(mode="json") for source in sources],
        "answer": response.answer,
        "retrieval_relevance": retrieval_relevance,
        "retrieval_rank": rank,
        "expected_topic_match": expected_topic_match,
        "groundedness": groundedness,
        "citation_correctness": citation_correctness,
        "answer_relevance": answer_relevance,
        "out_of_domain_behavior": out_of_domain,
        "measurements": {
            "retrieved_count": len(sources),
            "cited_labels": labels,
            "valid_citations": valid_citations,
            "expected_terms_present": expected_terms_present,
            "actionable_language_present": actionable,
        },
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None
    count = len(results)
    ranked_results = [result for result in results if result["retrieval_rank"] is not None]
    return {
        "measured_cases": count,
        "retrieval_relevance_at_k": sum(result["retrieval_relevance"] for result in results) / count,
        "retrieval_mean_reciprocal_rank": (
            sum(1 / result["retrieval_rank"] for result in ranked_results) / len(ranked_results)
            if ranked_results
            else None
        ),
        "groundedness_rate": sum(result["groundedness"] for result in results) / count,
        "citation_correctness_rate": sum(result["citation_correctness"] for result in results) / count,
        "answer_relevance_rate": sum(result["answer_relevance"] for result in results) / count,
        "out_of_domain_rate": sum(result["out_of_domain_behavior"] for result in results) / count,
    }


async def run(dataset_path: Path, provider_name: str | None) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    settings = get_settings()
    if provider_name:
        settings = settings.model_copy(update={"default_llm_provider": provider_name})
    embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dimensions)
    provider = get_llm_provider(settings)
    results: list[dict[str, Any]] = []
    async with AsyncSessionFactory() as session:
        engine = GroundedRAGEngine(SemanticRetriever(session, embedder, settings), provider, settings)
        for case in dataset:
            response = await engine.answer(case["user_question"])
            results.append(evaluate_case(case, response))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "provider": provider.name,
        "cases": results,
        "metrics": aggregate(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the grounded RAG evaluation against the configured database and provider.")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parents[1] / "evaluation" / "dataset.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--provider", choices=("ollama", "cloud", "openai"))
    args = parser.parse_args()
    try:
        report = asyncio.run(run(args.dataset, args.provider))
    except Exception as error:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset": str(args.dataset),
            "metrics": None,
            "execution_error": str(error),
        }
        exit_code = 2
    else:
        exit_code = 0
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())