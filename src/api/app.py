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
from src.api.schemas import (
    CVAdaptationRequest,
    ExplanationRequest,
    MatchingRequest,
    MyTutorialOrchestrationRequest,
)
from src.contracts.beauty_kit import BeautyKit, BeautyKitProduct, ProductCapability
from src.contracts.cv_adaptation import CVAdaptation
from src.contracts.explanation import LLMExplanation
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingResult
from src.contracts.my_tutorial import MyTutorialResponse
from src.db.repositories import (
    get_beauty_kit,
    get_beauty_kit_by_id,
    get_product_capability,
    get_recipe,
    list_product_capabilities,
    save_parser_run,
    load_fixture,
    save_beauty_kit,
    save_matching_result,
    save_product_capability,
    save_recipe,
    save_tutorial_explanation_run,
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
from src.services.product_matching import ProductMatchingService
from src.services.my_tutorial_orchestrator import (
    MyTutorialOrchestrationError,
    MyTutorialOrchestrator,
)
from src.services.tutorial_explanation import (
    ExplanationProvider,
    TutorialExplanationService,
)


FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


def _seed_week1_fixtures(session: Session) -> None:
    """Make the checked-in sample kit available for local demo requests."""
    if get_beauty_kit(session) is None:
        save_beauty_kit(
            session,
            BeautyKit.model_validate(load_fixture(FIXTURES_DIR / "beauty_kit_v1.json")),
        )
    capability_catalog = load_fixture(FIXTURES_DIR / "product_capabilities_demo_v1.json")
    for payload in capability_catalog["capabilities"]:
        capability = ProductCapability.model_validate(payload)
        if get_product_capability(session, capability.capability_id) is None:
            save_product_capability(session, capability)


def create_app(
    database_url: str | None = None,
    parser: TutorialParser | None = None,
    debug_runs: bool | None = None,
    explanation_provider: ExplanationProvider | None = None,
    product_matcher: ProductMatchingService | None = None,
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
    app.state.tutorial_explanation = TutorialExplanationService(explanation_provider)
    app.state.product_matcher = product_matcher or ProductMatchingService()
    app.state.my_tutorial_orchestrator = MyTutorialOrchestrator(
        matcher=app.state.product_matcher,
        explanation=app.state.tutorial_explanation,
    )
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

    def record_tutorial_explanation_run(run) -> None:
        if not app.state.debug_runs:
            return
        with session_factory() as session:
            save_tutorial_explanation_run(session, run)
        log_event(
            "tutorial_explanation_run_persisted",
            module="api",
            request_id=run.request_id,
            run_id=run.run_id,
            recipe_id=run.recipe_id,
            step_index=run.step_index,
            action_id=run.action_id,
            face_profile_version=run.face_profile_version,
            applied_rules=run.applied_rules,
            generator_version=run.explanation_generator_version,
            provider_name=run.provider_name,
            model_name=run.model_name,
            fallback_used=run.fallback_used,
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

    @app.post("/beauty-kit/products", response_model=BeautyKit, status_code=201)
    def add_beauty_kit_product(product: BeautyKitProduct, request: Request):
        session = session_for(request)
        try:
            beauty_kit = get_beauty_kit(session)
            if beauty_kit is None:
                raise APIError("beauty_kit_not_found", "Beauty Kit was not found.", status_code=404)
            if any(item.product_id == product.product_id for item in beauty_kit.products):
                raise APIError(
                    "product_already_exists", "Product already exists in Beauty Kit.",
                    {"product_id": product.product_id}, 409,
                )
            updated = beauty_kit.model_copy(
                update={"products": [*beauty_kit.products, product]}
            )
            save_beauty_kit(session, updated)
            return updated
        finally:
            session.close()

    @app.put("/beauty-kit/products/{product_id}", response_model=BeautyKit)
    def update_beauty_kit_product(
        product_id: str, product: BeautyKitProduct, request: Request
    ):
        if product.product_id != product_id:
            raise APIError(
                "product_id_mismatch", "Path and payload product_id must match.", status_code=400
            )
        session = session_for(request)
        try:
            beauty_kit = get_beauty_kit(session)
            if beauty_kit is None:
                raise APIError("beauty_kit_not_found", "Beauty Kit was not found.", status_code=404)
            if not any(item.product_id == product_id for item in beauty_kit.products):
                raise APIError(
                    "product_not_found", "Product was not found in Beauty Kit.",
                    {"product_id": product_id}, 404,
                )
            updated = beauty_kit.model_copy(
                update={
                    "products": [
                        product if item.product_id == product_id else item
                        for item in beauty_kit.products
                    ]
                }
            )
            save_beauty_kit(session, updated)
            return updated
        finally:
            session.close()

    @app.delete("/beauty-kit/products/{product_id}", response_model=BeautyKit)
    def remove_beauty_kit_product(product_id: str, request: Request):
        session = session_for(request)
        try:
            beauty_kit = get_beauty_kit(session)
            if beauty_kit is None:
                raise APIError("beauty_kit_not_found", "Beauty Kit was not found.", status_code=404)
            products = [item for item in beauty_kit.products if item.product_id != product_id]
            if len(products) == len(beauty_kit.products):
                raise APIError(
                    "product_not_found", "Product was not found in Beauty Kit.",
                    {"product_id": product_id}, 404,
                )
            updated = beauty_kit.model_copy(update={"products": products})
            save_beauty_kit(session, updated)
            return updated
        finally:
            session.close()

    @app.get("/product-capabilities", response_model=list[ProductCapability])
    def product_capabilities(request: Request):
        session = session_for(request)
        try:
            return list_product_capabilities(session)
        finally:
            session.close()

    @app.put(
        "/product-capabilities/{capability_id}", response_model=ProductCapability
    )
    def update_product_capability(
        capability_id: str, capability: ProductCapability, request: Request
    ):
        if capability.capability_id != capability_id:
            raise APIError(
                "capability_id_mismatch",
                "Path and payload capability_id must match.",
                status_code=400,
            )
        session = session_for(request)
        try:
            save_product_capability(session, capability)
            return capability
        finally:
            session.close()

    @app.post("/matching", response_model=MatchingResult)
    def match_products(payload: MatchingRequest, request: Request):
        session = session_for(request)
        try:
            recipe = payload.recipe or get_recipe(session, payload.recipe_id or "")
            if recipe is None:
                raise APIError("recipe_not_found", "Recipe was not found.", {"recipe_id": payload.recipe_id}, 404)
            capabilities = payload.capabilities or list_product_capabilities(session)
            result = request.app.state.product_matcher.match(
                recipe,
                payload.beauty_kit,
                capabilities,
                request_id=request.state.request_id,
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

    @app.post("/tutorials/my-tutorial", response_model=MyTutorialResponse)
    def build_my_tutorial(
        payload: MyTutorialOrchestrationRequest, request: Request
    ):
        session = session_for(request)
        try:
            recipe = payload.recipe or get_recipe(session, payload.recipe_id or "")
            if recipe is None:
                raise APIError(
                    "recipe_not_found", "Recipe was not found.",
                    {"recipe_id": payload.recipe_id}, 404,
                )
            beauty_kit = payload.beauty_kit or get_beauty_kit_by_id(
                session, payload.beauty_kit_id or ""
            )
            if beauty_kit is None:
                raise APIError(
                    "beauty_kit_not_found", "Beauty Kit was not found.",
                    {"beauty_kit_id": payload.beauty_kit_id}, 404,
                )
            capabilities = payload.capabilities or list_product_capabilities(session)
            return request.app.state.my_tutorial_orchestrator.generate(
                recipe=recipe,
                beauty_kit=beauty_kit,
                face_profile=payload.face_profile,
                face_profile_id=payload.face_profile_id,
                capabilities=capabilities,
                target_effect=payload.target_effect,
                tutorial_id=payload.tutorial_id,
                request_id=request.state.request_id,
                explanation_run_observer=record_tutorial_explanation_run,
            )
        except MyTutorialOrchestrationError as exc:
            log_event(
                "my_tutorial_orchestration_failure",
                module="api",
                request_id=request.state.request_id,
                recipe_id=payload.recipe_id or (
                    payload.recipe.recipe_id if payload.recipe else None
                ),
                error_code="my_tutorial_orchestration_failed",
                details=str(exc),
            )
            raise APIError(
                "my_tutorial_orchestration_failed",
                "My Tutorial orchestration failed.",
                str(exc),
                422,
            ) from exc
        finally:
            session.close()

    return app


app = create_app()
