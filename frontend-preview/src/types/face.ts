export interface FaceScanQuality {
  brightness: number;
  yaw: number;
  pitch: number;
  roll: number;
  faceCoverage: number;
  occlusion: number;
  valid: boolean;
}
export interface FaceProfile {
  proportions: { label: string; value: string }[];
  structure: { label: string; value: string }[];
  undertone: string;
  value: string;
  chroma: string;
  contrast: string;
  season: string;
}
