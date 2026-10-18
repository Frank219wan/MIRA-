"""Multipart transport for the existing stable-scan pipeline; no CV algorithms."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import UploadFile

from src.api.errors import APIError

MAX_FRAMES = 20
MAX_FRAME_BYTES = 10 * 1024 * 1024


def scan_uploaded_frames(images: list[UploadFile], input_is_mirrored: bool = False) -> dict:
    # Keep optional native dependencies isolated from the other API endpoints.
    try:
        from src.eye_landmarks import process_eye_geometry
        from src.face_landmarker import DEFAULT_MODEL_PATH, FaceLandmarkerError
        from src.face_profile import FaceProfileError
        from src.face_scan_aggregator import (
            FaceScanAggregator, FaceScanAggregationError, MIN_VALID_FRAMES,
            validate_face_profile,
        )
    except ImportError as exc:
        raise APIError("face_scan_unavailable", "Face scan dependencies are unavailable.", status_code=503) from exc

    if len(images) > MAX_FRAMES:
        raise APIError("invalid_request_payload", "Upload at most 20 images.", status_code=413)
    model_path = Path(os.environ.get("MIRA_FACE_MODEL_PATH", str(DEFAULT_MODEL_PATH)))
    if not model_path.is_file():
        raise APIError("face_scan_unavailable", "Face Landmarker model is unavailable.", status_code=503)

    aggregator = FaceScanAggregator()
    valid_count = 0
    failed_frames = []
    with TemporaryDirectory(prefix="mira-face-scan-") as temporary:
        directory = Path(temporary)
        for index, upload in enumerate(images, start=1):
            frame_id = f"frame_{index:03d}"
            try:
                # Bounded read and generated filenames; original names never become paths.
                content = upload.file.read(MAX_FRAME_BYTES + 1)
                if not content:
                    raise ValueError("Empty image.")
                if len(content) > MAX_FRAME_BYTES:
                    raise ValueError("Image exceeds 10 MiB.")
                image_path = directory / f"{frame_id}.image"
                image_path.write_bytes(content)
                profile_path = directory / f"{frame_id}_profile.json"
                process_eye_geometry(
                    image_path=image_path,
                    model_path=model_path,
                    debug_output_path=directory / f"{frame_id}_debug.jpg",
                    json_output_path=directory / f"{frame_id}_geometry.json",
                    profile_output_path=profile_path,
                    input_is_mirrored=input_is_mirrored,
                )
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                validate_face_profile(profile)
                aggregator.add_profile(profile, frame_id=frame_id)
                valid_count += 1
            except (FaceLandmarkerError, FaceProfileError, FaceScanAggregationError, OSError, ValueError) as exc:
                reason = str(exc).replace(str(directory), "temporary_upload")
                aggregator.add_failure(frame_id=frame_id, reason=reason)
                failed_frames.append({"frame_id": frame_id, "valid": False, "reason": reason})
        if valid_count < MIN_VALID_FRAMES:
            raise APIError(
                "insufficient_valid_frames", "Stable Face Scan requires at least 3 valid profiles.",
                {"frame_count": len(images), "valid_frame_count": valid_count,
                 "min_valid_frames": MIN_VALID_FRAMES, "failed_frames": failed_frames},
            )
        try:
            return aggregator.finalize()
        except FaceScanAggregationError as exc:
            raise APIError("invalid_request_payload", "Face scan aggregation failed.", str(exc)) from exc
