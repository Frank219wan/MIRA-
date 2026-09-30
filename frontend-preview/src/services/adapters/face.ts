import type { FaceProfileDTO } from "../api/dto";
import type { FaceProfile } from "../../types/face";
import { faceProfile as mock } from "../../mocks/faceProfile";
export function adaptFaceProfile(dto: FaceProfileDTO) {
  if (dto.version !== "0.3")
    throw new Error("Unsupported Face Profile version");
  const g = dto.eye_geometry,
    s = dto.symmetry;
  const numbers = [
    g?.eye_tail_angle?.left,
    g?.eye_tail_angle?.right,
    g?.eye_tail_angle?.mean,
    g?.eye_spacing_ratio,
    g?.relative_eye_length?.left,
    g?.relative_eye_length?.right,
    g?.relative_eye_length?.mean,
    g?.eye_width_height_ratio?.left,
    g?.eye_width_height_ratio?.right,
    g?.eye_width_height_ratio?.mean,
    g?.brow_eye_ratio?.left,
    g?.brow_eye_ratio?.right,
    g?.brow_eye_ratio?.mean,
    g?.lower_lid_space_ratio?.left,
    g?.lower_lid_space_ratio?.right,
    g?.lower_lid_space_ratio?.mean,
    g?.inner_corner_angle?.left_deg,
    g?.inner_corner_angle?.right_deg,
    g?.inner_corner_angle?.mean_deg,
    s?.eye_width,
    s?.eye_height,
    s?.eye_aspect_ratio,
    s?.eye_tail_angle_difference,
  ];
  if (
    !numbers.every((n) => typeof n === "number" && Number.isFinite(n)) ||
    !dto.raw_geometry_reference ||
    !dto.confidence
  )
    throw new Error("Invalid Face Profile geometry");
  const profile: FaceProfile = {
    proportions: [
      {
        label: "双眼间距",
        value: `约 ${g.eye_spacing_ratio.toFixed(2)} 个眼宽`,
      },
      { label: "眉眼距离 / 眼宽", value: g.brow_eye_ratio.mean.toFixed(2) },
    ],
    structure: [
      {
        label: "眼尾走势",
        value: `${g.eye_tail_angle.mean > 0 ? "上扬" : g.eye_tail_angle.mean < 0 ? "下行" : "水平"} ${g.eye_tail_angle.mean.toFixed(2)}°`,
      },
      { label: "左右眼宽差异", value: `${(s.eye_width * 100).toFixed(1)}%` },
      { label: "左右眼高差异", value: `${(s.eye_height * 100).toFixed(1)}%` },
      {
        label: "左右眼宽高比差异",
        value: `${(s.eye_aspect_ratio * 100).toFixed(1)}%`,
      },
      {
        label: "左右眼尾角差异",
        value: `${s.eye_tail_angle_difference.toFixed(2)}°`,
      },
    ],
    // v0.3 measures geometry only; these remain independent demo color values.
    undertone: mock.undertone,
    value: mock.value,
    chroma: mock.chroma,
    contrast: mock.contrast,
    season: mock.season,
  };
  return {
    profile,
    provenance: { geometry: "face-profile", color: "mock" } as const,
    raw: dto,
  };
}
