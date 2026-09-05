from pathlib import Path

import pytest

from app.rag.ingestion import IngestionError, build_chunks, parse_transcript_file


def test_parser_extracts_frontmatter_and_timestamp(tmp_path: Path) -> None:
    source = tmp_path / "episode.md"
    source.write_text("---\ntitle: Growth Systems\nguest: Ada Lovelace\npublished_at: 2025-01-02T00:00:00+00:00\n---\n# Retention\n[00:01:30] Keep users focused on their first success.\n", encoding="utf-8")

    parsed = parse_transcript_file(source)

    assert parsed.metadata.title == "Growth Systems"
    assert parsed.metadata.guest_name == "Ada Lovelace"
    assert parsed.segments[0].start_seconds == 90.0
    assert parsed.segments[0].topic == "Retention"


def test_chunking_is_deterministic_and_overlaps(tmp_path: Path) -> None:
    source = tmp_path / "episode.txt"
    source.write_text("title: Chunking\n\n" + " ".join(f"word{i}" for i in range(1_300)), encoding="utf-8")
    parsed = parse_transcript_file(source)

    first, second = build_chunks(parsed), build_chunks(parsed)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert len(first) == 3
    assert first[0].token_count == 650
    assert first[1].content.split()[0] == "word550"


def test_parser_rejects_unsupported_extension(tmp_path: Path) -> None:
    source = tmp_path / "episode.pdf"
    source.write_text("not a transcript", encoding="utf-8")

    with pytest.raises(IngestionError, match="Markdown and TXT"):
        parse_transcript_file(source)
