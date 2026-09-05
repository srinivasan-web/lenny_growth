# RAG Evaluation

## Method

The evaluation dataset contains five manually labeled questions: four in-domain product-growth topics and one weather question outside the podcast archive. Each case records its expected topic, an expected source substring, and answer characteristics such as citation requirements, actionable language, and expected terms.

The runner uses the production `SemanticRetriever` and `GroundedRAGEngine` with the configured database, embedding model, and LLM provider. It does not use test doubles. The expected source values are matched against retrieved episode, guest, topic, and URL metadata.

The measurements are:

- **Retrieval relevance:** whether the expected source is retrieved, or whether an out-of-domain case returns no sources.
- **Retrieval ranking:** reciprocal rank of the first matching expected source.
- **Groundedness:** whether citations point to returned sources, or whether an out-of-domain answer is the canonical insufficient-evidence response.
- **Citation correctness:** whether cited labels are valid and include the expected retrieved source.
- **Answer relevance:** whether expected terms appear and required actionable language is present.
- **Out-of-domain behavior:** whether the out-of-domain case returns no sources and refuses to answer.

Metrics are calculated only from cases that actually execute. If the database, embeddings, or provider is unavailable, the command emits `metrics: null` and an `execution_error`; it never fabricates scores.

## Command

From `backend/`:

```powershell
python scripts/evaluate_rag.py --provider ollama --output evaluation/reports/latest.json
```

Use `--provider openai` or `--provider cloud` when those credentials are configured. The report contains every prediction, retrieved source, citation label, and aggregate measurement. Update `evaluation/dataset.json` when the archive gains curated cases or source expectations.