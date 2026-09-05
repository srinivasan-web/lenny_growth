import argparse
import asyncio
from pathlib import Path

from app.config import get_settings
from app.database import AsyncSessionFactory
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.ingestion import TranscriptIngestionService


async def main(path: Path) -> None:
    settings = get_settings()
    embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dimensions)
    async with AsyncSessionFactory() as session:
        result = await TranscriptIngestionService(session, embedder).ingest_file(path)
    print(f"{result.status}: episode={result.episode_id} transcript={result.transcript_id} chunks={result.chunk_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest one Markdown or TXT podcast transcript.")
    parser.add_argument("path", type=Path)
    asyncio.run(main(parser.parse_args().path))
