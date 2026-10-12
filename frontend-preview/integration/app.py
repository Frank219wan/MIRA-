"""Local HTTP boundary for MIRA modules. Start with latest backend on PYTHONPATH.
No algorithms live here; the desktop source directories remain untouched.
"""
from fastapi import File, Form, UploadFile
from pydantic import Field
from src.api.app import app
from src.api.errors import APIError
from src.contracts.common import ContractModel
from src.personalization_engine import personalize_recipe, PersonalizationEngineError
from src.special_area_tutorial_adapter import adapt_special_area_tutorial
from src.special_area_profile import SpecialAreaProfileError
from integration.face_scan_transport import scan_uploaded_frames

class PersonalizationRequest(ContractModel):
    face_profile: dict
    standard_recipe: dict
    target_effect: str

class SpecialAreaRequest(ContractModel):
    profile: dict = Field(description="User-selected Special Area Profile v0.1; no image upload.")


@app.post('/face-scan')
def face_scan(images: list[UploadFile] = File(...), input_is_mirrored: bool = Form(False)):
    return scan_uploaded_frames(images, input_is_mirrored)

@app.post('/personalization')
def personalization(payload: PersonalizationRequest):
    try:
        return personalize_recipe(payload.face_profile, payload.standard_recipe, payload.target_effect)
    except PersonalizationEngineError as exc:
        raise APIError('invalid_request_payload', 'Personalization validation failed.', str(exc)) from exc

@app.post('/special-area-guidance')
def special_area_guidance(payload: SpecialAreaRequest):
    try:
        return adapt_special_area_tutorial(payload.profile)
    except SpecialAreaProfileError as exc:
        raise APIError('invalid_request_payload', 'Special area validation failed.', str(exc)) from exc
