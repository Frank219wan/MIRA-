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
  product_capability_requirement?: {
    product_category: string;
    color_families: string[];
    finishes: string[];
    depths: string[];
    pigmentations: string[];
    textures: string[];
    functions: string[];
  } | null;
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
    score?: number | null;
    verification_status?: "verified" | "insufficient_data";
    reason?: string;
    difference?: string;
    impact?: string;
    missing_capabilities?: string[];
    hard_constraints?: string[];
    required_capabilities?: Record<string, unknown>;
    capability_checks?: {
      key: string;
      label: string;
      matched: boolean;
      score: number;
      weight: number;
      verified: boolean;
    }[];
  }[];
}
export interface FaceProfileDTO {
  version: "0.3";
  eye_geometry: {
    eye_tail_angle: Bilateral;
    eye_spacing_ratio: number;
    relative_eye_length: Bilateral;
    eye_width_height_ratio: Bilateral;
    brow_eye_ratio: Bilateral;
    lower_lid_space_ratio: Bilateral;
    inner_corner_angle: {
      left_deg: number;
      right_deg: number;
      mean_deg: number;
    };
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

export type EngineActionId = "A02" | "A04";
export interface EngineActionDTO {
  action_id: EngineActionId;
  parameters: Record<string, number>;
}
export interface PersonalizationRequestDTO {
  face_profile: FaceProfileDTO;
  standard_recipe: { recipe_id: string; actions: EngineActionDTO[] };
  target_effect: "cat_eye";
}
export interface PersonalizationAdjustmentDTO {
  rule_ids: string[];
  feature_path: string;
  feature_value: number;
  parameter: string;
  operation: string;
  adjustment_value: number;
  original_value: number;
  personalized_value: number;
}
export interface PersonalizedEngineActionDTO {
  action_id: EngineActionId;
  original_parameters: Record<string, number>;
  personalized_parameters: Record<string, number>;
  applied_rules: string[];
  adjustments: PersonalizationAdjustmentDTO[];
}
export interface PersonalizationResultDTO {
  recipe_id: string;
  target_effect: "cat_eye";
  personalized_actions: PersonalizedEngineActionDTO[];
}

export interface FaceScanResultDTO {
  aggregated_face_profile: FaceProfileDTO;
  valid_frame_count: number;
  quality_information: {
    frames: { frame_id: string; valid: boolean; reason: string | null }[];
  };
}
