"""Parse uploaded media through a configured real vision provider."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import shutil
from fastapi import APIRouter, Request
from pydantic import Field, ValidationError
from src.api.errors import APIError
from src.contracts.common import ContractModel
from src.contracts.makeup import StandardRecipe
from src.db.repositories import save_recipe
from src.services.tutorial_parser import TutorialMediaInput, MockTutorialVisionProvider
from src.services.tutorial_prompt import TUTORIAL_PARSER_PROMPT
from integration.media_preview import resolve_preview

router = APIRouter()

class UploadParseRequest(ContractModel):
    upload_id: str
    title: str = Field(min_length=1, max_length=300)

@router.post('/tutorials/parse-upload', response_model=StandardRecipe)
def parse_upload(payload: UploadParseRequest, request: Request):
    source = resolve_preview(payload.upload_id)
    provider = request.app.state.tutorial_parser.provider
    if isinstance(provider, MockTutorialVisionProvider) or getattr(provider, 'provider_name', None) == 'mock':
        raise APIError('vision_not_configured', '文件已上传，真实教程识别服务尚未配置；本次未生成拆解结果。', status_code=503)
    kind = 'video' if source.suffix in {'.mp4', '.mov', '.webm'} else 'frame_directory'
    with TemporaryDirectory(prefix='mira-parse-') as folder:
        local = Path(folder) / source.name
        shutil.copyfile(source, local)
        media = TutorialMediaInput(media_path=local if kind == 'video' else Path(folder),
                                   media_kind=kind, recipe_id='recipe-' + uuid4().hex, title=payload.title)
        try:
            raw = provider.extract_action_units(media, TUTORIAL_PARSER_PROMPT + '\nOnly report observable actions from the supplied media. Do not invent steps or timestamps. Return the actual number of actions; do not force five steps. Use Chinese descriptions. If no tutorial actions are observable, return an empty action_units list.')
            if isinstance(raw, dict) and raw.get('action_units') == []:
                raise APIError('no_tutorial_actions', '未找到可拆解的上妆步骤，请上传包含操作过程或步骤说明的素材。', status_code=422)
            # Use the existing reusable contract, without the demo parser's five-step restriction.
            recipe = StandardRecipe.model_validate({
                'recipe_id': media.recipe_id, 'title': payload.title,
                'source_media_path': 'upload:' + payload.upload_id,
                'action_units': raw['action_units'],
            })
        except APIError:
            raise
        except (ValidationError, KeyError, TypeError) as exc:
            raise APIError('invalid_parser_result', '解析结果格式不完整，请重试。', status_code=502) from exc
        except Exception as exc:
            raise APIError('parser_unavailable', '教程识别服务暂不可用，请稍后重试。', status_code=502) from exc
    with request.app.state.session_factory() as session:
        save_recipe(session, recipe, kind)
    return recipe
