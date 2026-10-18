import { request } from './api/client';
import { getStaticFace } from './staticFace';
import { getFaceProfileDTO } from './face';
type Point = { x_norm: number; y_norm: number };
export interface StaticGuidance { image_id: string; reference_id: string; source: string; shapes: { guidance_type: string; side: string; anchor?: Point; endpoint?: Point; polygon?: Point[] }[] }
export const getCuratedReference = () => request<{title:string; description:string; steps:{action_id:'A02'|'A04';title:string;instruction:string}[]}>('/references/cat-eye');
export async function getStaticGuidance(action: 'A02'|'A04') {
  const face = getStaticFace(), profile = getFaceProfileDTO();
  if (!face || !profile) throw new Error('请重新扫描，取得本人的照片和面部档案。');
  const result = await request<StaticGuidance>('/guidance/static', {image_id:face.id,reference_id:'cat_eye_main_demo',action_id:action,landmarks:face.landmarks,face_profile:profile});
  if (getStaticFace()?.id !== face.id || !getFaceProfileDTO() || result.image_id !== face.id) throw new Error('照片已更换，请重新查看指导。');
  if (!Array.isArray(result.shapes) || result.shapes.length !== 2) throw new Error('定位结果不完整。');
  return {image:face.image, ...result};
}
