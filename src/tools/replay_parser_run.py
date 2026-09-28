"""Replay parser schema validation from stored debug output without a model call."""

from __future__ import annotations

import argparse
import json
import sys

from src.db.repositories import get_parser_run
from src.db.session import create_session_factory, create_week1_engine
from src.services.tutorial_parser import (
    MockTutorialVisionProvider,
    TutorialMediaInput,
    TutorialParser,
    TutorialParserError,
)


def replay_parser_run(run_id: str, database_url: str | None = None):
    """Return a revalidated recipe using only persisted raw provider output."""
    engine = create_week1_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        run = get_parser_run(session, run_id)
        if run is None:
            raise ValueError(f"Parser run not found: {run_id}")
        if run.raw_output_json is None:
            raise ValueError(f"Parser run has no stored raw output: {run_id}")
        raw_output = json.loads(run.raw_output_json)
        media = TutorialMediaInput(
            media_path=run.input_media_path,
            media_kind=run.input_media_kind,
            recipe_id=run.recipe_id,
            title=run.tutorial_title,
        )
    engine.dispose()
    return TutorialParser(MockTutorialVisionProvider()).validate_provider_output(
        media, raw_output
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Revalidate a stored parser run without calling a model."
    )
    parser.add_argument("run_id")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    try:
        recipe = replay_parser_run(args.run_id, args.database_url)
    except (ValueError, TutorialParserError, json.JSONDecodeError) as exc:
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 1
    print(recipe.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
