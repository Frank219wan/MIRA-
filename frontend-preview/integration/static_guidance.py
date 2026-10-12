"""Static guidance: existing reference mapping and geometry; no tracking algorithm."""
import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.api.errors import APIError
from src.reference_package import package_existing_reference, personalize_reference_package
from src.ar_guidance import build_a04_guidance, build_a02_guidance
from src.face_scan_aggregator import validate_face_profile
import src.reference_package as reference_module

router = APIRouter()
REFERENCE_FILE = Path(reference_module.__file__).parents[1] / 'data/fixtures/main_demo/main_demo_reference.json'

class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
class StaticRequest(BaseModel):
    image_id: str = Field(min_length=1, max_length=100)
    action_id: Literal['A02', 'A04']
    landmarks: list[Point] = Field(min_length=468, max_length=478)
    face_profile: dict
    reference_id: Literal['cat_eye_main_demo']

@router.get('/references/cat-eye')
def reference():
    return {'reference_id':'cat_eye_main_demo', 'title':'猫眼位置参考', 'source':'curated-reference',
            'description':'人工整理的下眼睑与眼线参考，使用已有猫眼参考参数；不代表上传图片或视频的识别结果。',
            'steps':[{'action_id':'A02','title':'下眼睑范围','instruction':'从外眼角向内轻扫，按目标区域少量晕染。'},
                     {'action_id':'A04','title':'眼尾方向','instruction':'沿参考方向分段画出眼尾，少量延伸并对照镜中效果。'}]}

@router.post('/guidance/static')
def static_guidance(payload: StaticRequest):
    try:
        validate_face_profile(payload.face_profile)
        package = package_existing_reference(json.loads(REFERENCE_FILE.read_text()))
        result = personalize_reference_package(package, payload.face_profile, sample_id='static-photo')
        def point(i):
            p = payload.landmarks[i]
            return {'x_norm':p.x, 'y_norm':p.y}
        shapes = []
        for side, inner, outer, lower in [('left',362,263,[263,373,374,380,382,362]),('right',133,33,[33,144,145,153,155,133])]:
            landmarks = {'eye_inner':point(inner),'eye_outer':point(outer),'lower_lid_path':[point(i) for i in lower]}
            shapes.append(build_a04_guidance(landmarks,result['A04'],side,source='curated-reference') if payload.action_id == 'A04' else build_a02_guidance(landmarks,result['A02'],side,source='curated-reference'))
        return {'image_id':payload.image_id,'reference_id':payload.reference_id,'source':'backend-static-reference','shapes':shapes}
    except (ValueError, KeyError, TypeError) as exc:
        raise APIError('invalid_static_guidance','此照片暂不能生成准确定位，请重新扫描。',status_code=422) from exc
