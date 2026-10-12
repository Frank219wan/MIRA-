"""Temporary uploads for preview only; never invoke the tutorial parser."""
from pathlib import Path
from tempfile import gettempdir
from time import time
from uuid import uuid4
import re
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from src.api.errors import APIError

router = APIRouter()
DIRECTORY = Path(gettempdir()) / 'mira-tutorial-previews'
MAX_BYTES = 100 * 1024 * 1024
TYPES = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
         'video/mp4': '.mp4', 'video/quicktime': '.mov', 'video/webm': '.webm'}

def cleanup():
    DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    for path in DIRECTORY.iterdir():
        if path.is_file() and time() - path.stat().st_mtime > 3600:
            path.unlink(missing_ok=True)

@router.post('/media/preview')
def upload_preview(file: UploadFile = File(...)):
    cleanup()
    mime = file.content_type or ''
    if mime not in TYPES:
        raise APIError('unsupported_media', '请选择 JPG、PNG、WebP、MP4、MOV 或 WebM 文件。', status_code=415)
    name = uuid4().hex + TYPES[mime]
    path = DIRECTORY / name
    size = 0
    try:
        with path.open('xb') as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise APIError('file_too_large', '文件不能超过 100 MB。', status_code=413)
                output.write(chunk)
        if size == 0:
            raise APIError('empty_file', '文件为空，请重新选择。')
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {'upload_id': name, 'preview_path': '/media/preview/' + name, 'kind': mime.split('/')[0]}

def resolve_preview(name: str):
    cleanup()
    if not re.fullmatch(r'[0-9a-f]{32}\.(jpg|png|webp|mp4|mov|webm)', name):
        raise APIError('not_found', '预览不存在或已过期。', status_code=404)
    path = DIRECTORY / name
    if not path.is_file():
        raise APIError('not_found', '预览不存在或已过期。', status_code=404)
    return path

@router.get('/media/preview/{name}')
def get_preview(name: str):
    path = resolve_preview(name)
    mime = next(m for m, suffix in TYPES.items() if suffix == path.suffix)
    return FileResponse(path, media_type=mime, headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})
