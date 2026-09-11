"""Minimal FastAPI application for the Week 1 demo flow."""

from __future__ import annotations

import re
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from src.api.errors import (
    APIError,
    api_error_handler,
    request_validation_handler,
    unexpected_error_handler,
)
from src.api.schemas import CVAdaptationRequest, ExplanationRequest, MatchingRequest
from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.cv_adaptation import CVAdaptation
from src.contracts.explanation import LLMExplanation
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingItem, MatchingResult
from src.db.repositories import (
    get_beauty_kit,
    get_recipe,
    save_parser_run,
    load_fixture,
    save_beauty_kit,
    save_matching_result,
    save_product_capability,
    save_recipe,
)
from src.db.session import (
    PROJECT_ROOT,
    bootstrap_database,
    create_session_factory,
    create_week1_engine,
    debug_runs_from_environment,
)
from src.observability import log_event
from src.services.tutorial_parser import (
    MockTutorialVisionProvider,
    TutorialMediaInput,
    TutorialParserError,
    TutorialParser,
)


FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


def _seed_week1_fixtures(session: Session) -> None:
    """Make the checked-in sample kit available for local demo requests."""
    if get_beauty_kit(session) is None:
        save_beauty_kit(
            session,
            BeautyKit.model_validate(load_fixture(FIXTURES_DIR / "beauty_kit_v1.json")),
        )
        save_product_capability(
            session,
            ProductCapability.model_validate(
                load_fixture(FIXTURES_DIR / "product_capability_v1.json")
            ),
        )


def create_app(
    database_url: str | None = None,
    parser: TutorialParser | None = None,
    debug_runs: bool | None = None,
) -> FastAPI:
    engine = create_week1_engine(database_url)
    bootstrap_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        _seed_week1_fixtures(session)

    app = FastAPI(title="MIRA Week 1 API", version="0.1.0")
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.tutorial_parser = parser or TutorialParser(MockTutorialVisionProvider())
    app.state.debug_runs = debug_runs if debug_runs is not None else debug_runs_from_environment()
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    @app.middleware("http")
    async def request_tracing(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID")
        request_id = supplied if supplied and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", supplied) else str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        log_event(
            "request_start",
            module="api",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "request_exception",
                module="api",
                request_id=request_id,
                error_code="internal_error",
            )
            raise
        response.headers["X-Request-ID"] = request_id
        log_event(
            "request_end",
            module="api",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return response

    def session_for(request: Request) -> Session:
        factory: sessionmaker[Session] = request.app.state.session_factory
        return factory()

    def record_parser_run(run) -> None:
        if not app.state.debug_runs:
            return
        with session_factory() as session:
            save_parser_run(session, run)
        log_event(
            "parser_run_persisted",
            module="api",
            request_id=run.request_id,
            run_id=run.run_id,
            duration_ms=run.duration_ms,
        )

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        return {
            "status": "ok",
            "service": "mira-week1-api",
            "request_id": request.state.request_id,
        }

    @app.post("/tutorials/parse", response_model=StandardRecipe)
    def parse_tutorial(media: TutorialMediaInput, request: Request):
        try:
            recipe = request.app.state.tutorial_parser.parse(
                media,
                request_id=request.state.request_id,
                run_observer=record_parser_run,
            )
        except TutorialParserError as exc:
            raise APIError("parser_failure", "Tutorial parsing failed.", str(exc)) from exc
        session = session_for(request)
        try:
            save_recipe(session, recipe, media.media_kind)
            log_event(
                "recipe_persistence_success",
                module="api",
                request_id=request.state.request_id,
                recipe_id=recipe.recipe_id,
                schema_version=recipe.schema_version,
            )
        finally:
            session.close()
        return recipe

    @app.get("/recipes/{recipe_id}", response_model=StandardRecipe)
    def retrieve_recipe(recipe_id: str, request: Request):
        session = session_for(request)
        try:
            recipe = get_recipe(session, recipe_id)
        finally:
            session.close()
        if recipe is None:
            raise APIError("recipe_not_found", "Recipe was not found.", {"recipe_id": recipe_id}, 404)
        return recipe

    @app.get("/beauty-kit", response_model=BeautyKit)
    def current_beauty_kit(request: Request):
        session = session_for(request)
        try:
            beauty_kit = get_beauty_kit(session)
        finally:
            session.close()
        if beauty_kit is None:
            raise APIError("internal_error", "Week 1 Beauty Kit fixture is unavailable.", status_code=500)
        return beauty_kit

    @app.post("/matching", response_model=MatchingResult)
    def matching_placeholder(payload: MatchingRequest, request: Request):
        session = session_for(request)
        try:
            recipe = payload.recipe or get_recipe(session, payload.recipe_id or "")
            if recipe is None:
                raise APIError("recipe_not_found", "Recipe was not found.", {"recipe_id": payload.recipe_id}, 404)
            log_event(
                "matching_placeholder_invoked",
                module="api",
                request_id=request.state.request_id,
                recipe_id=recipe.recipe_id,
                schema_version=recipe.schema_version,
            )
            result = MatchingResult(
                matching_id=f"match-{uuid4()}",
                recipe_id=recipe.recipe_id,
                beauty_kit_id=payload.beauty_kit.kit_id,
                items=[
                    MatchingItem(
                        step_index=unit.step_index,
                        status="unmatched",
                        note="Week 1 structural placeholder; no matching algorithm executed.",
                    )
                    for unit in recipe.action_units
                ],
            )
            save_matching_result(session, result)
            return result
        finally:
            session.close()

    @app.post("/cv-adaptation", response_model=CVAdaptation)
    def cv_adaptation_placeholder(payload: CVAdaptationRequest, request: Request):
        try:
            adaptation = CVAdaptation(recipe_id=payload.recipe.recipe_id, face_profile=payload.face_profile)
            log_event(
                "cv_adaptation_validation_success",
                module="api",
                request_id=request.state.request_id,
                recipe_id=payload.recipe.recipe_id,
                schema_version=payload.face_profile.get("version"),
            )
            return adaptation
        except ValidationError as exc:
            message = str(exc)
            code = "invalid_face_profile_version" if "Unsupported Face Profile version" in message else "invalid_request_payload"
            log_event(
                "cv_adaptation_validation_failure",
                module="api",
                request_id=request.state.request_id,
                recipe_id=payload.recipe.recipe_id,
                error_code=code,
            )
            raise APIError(code, "Face Profile validation failed.", exc.errors()) from exc

    @app.post("/explanations", response_model=LLMExplanation)
    def explanation_placeholder(payload: ExplanationRequest, request: Request):
        log_event(
            "explanation_placeholder_invoked",
            module="api",
            request_id=request.state.request_id,
            recipe_id=payload.recipe.recipe_id,
            schema_version=payload.recipe.schema_version,
        )
        return LLMExplanation(
            recipe_id=payload.recipe.recipe_id,
            matching_id=payload.matching.matching_id,
            explanation="Week 1 placeholder: explanation generation is not implemented.",
        )

    return app


app = create_app()
