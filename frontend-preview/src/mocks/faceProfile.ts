import type { FaceProfile, FaceScanQuality } from "../types/face";
export const quality: FaceScanQuality = {
  brightness: 0.78,
  yaw: 2,
  pitch: 1,
  roll: 0,
  faceCoverage: 0.65,
  occlusion: 0,
  valid: true,
};
export const faceProfile: FaceProfile = {
  proportions: [
    { label: "上庭 / 中庭 / 下庭", value: "1.0 : 1.05 : 1.0" },
    { label: "双眼间距", value: "约 1.1 个眼宽" },
    { label: "眉眼距离", value: "相对舒展" },
  ],
  structure: [
    { label: "眼型", value: "偏长杏眼" },
    { label: "眼睑", value: "内侧褶皱较窄" },
    { label: "眼尾走势", value: "轻微下行" },
    { label: "眼距", value: "略宽" },
  ],
  undertone: "偏暖",
  value: "中高明度",
  chroma: "柔和",
  contrast: "中等对比",
  season: "柔秋倾向",
};
