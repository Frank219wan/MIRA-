// HTTP boundary types mirror backend-reference. Domain types remain UI-owned.
export interface ActionUnitDTO {
  step_index: number;
  area: string;
  goal: string;
  product_requirement: string;
  tool: string;
  motion: string;
  intensity: string;
  target_result: string;
  time_range_seconds?: [number, number] | null;
  confidence?: number | null;
}
export interface StandardRecipeDTO {
  schema_version: "1.0";
  recipe_id: string;
  title: string;
  source_media_path: string;
  action_units: ActionUnitDTO[];
}
export interface TutorialMediaInputDTO {
  media_path: string;
  media_kind: "video" | "frame_directory";
  recipe_id: string;
  title: string;
}
export interface BeautyKitProductDTO {
  product_id: string;
  name: string;
  capability_ids: string[];
}
export interface BeautyKitDTO {
  schema_version: string;
  kit_id: string;
  name: string;
  products: BeautyKitProductDTO[];
}
export interface MatchingResultDTO {
  schema_version: string;
  matching_id: string;
  recipe_id: string;
  beauty_kit_id: string;
  items: {
    step_index: number;
    status: "matched" | "unmatched" | "substitution_candidate";
    product_id?: string | null;
    capability_id?: string | null;
    note?: string | null;
  }[];
}
export interface FaceProfileDTO {
  version: "0.1";
  eye_geometry: {
    eye_tail_angle: Bilateral;
    eye_spacing_ratio: number;
    brow_eye_ratio: Bilateral;
  };
  symmetry: {
    eye_width: number;
    eye_height: number;
    eye_aspect_ratio: number;
    eye_tail_angle_difference: number;
  };
  raw_geometry_reference: Record<string, unknown>;
  confidence: Record<string, unknown>;
}
interface Bilateral {
  left: number;
  right: number;
  mean: number;
}
export interface CVAdaptationDTO {
  schema_version: string;
  recipe_id: string;
  face_profile: FaceProfileDTO;
}
