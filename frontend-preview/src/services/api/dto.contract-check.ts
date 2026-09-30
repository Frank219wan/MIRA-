import type { FaceProfileDTO, MyTutorialResponseDTO } from "./dto";

// Compile-time witnesses: the frontend transport types can represent each
// frozen backend boundary. They are not runtime fixtures or UI mock data.
export const faceProfileContractWitness = {
  version: "0.3",
  eye_geometry: {
    eye_tail_angle: { left: 8, right: 9, mean: 8.5 },
    eye_spacing_ratio: 1.3,
    relative_eye_length: { left: 0.2, right: 0.21, mean: 0.205 },
    eye_width_height_ratio: { left: 2.4, right: 2.5, mean: 2.45 },
    brow_eye_ratio: { left: 0.6, right: 0.62, mean: 0.61 },
    lower_lid_space_ratio: { left: 0.14, right: 0.15, mean: 0.145 },
    inner_corner_angle: { left_deg: 60, right_deg: 62, mean_deg: 61 },
  },
  symmetry: {
    eye_width: 0.01,
    eye_height: 0.02,
    eye_aspect_ratio: 0.01,
    eye_tail_angle_difference: 1,
  },
  raw_geometry_reference: { source: "fixture" },
  confidence: { pose_normalized: true, expression_controlled: false },
} satisfies FaceProfileDTO;

export const myTutorialContractWitness = {
  schema_version: "0.2",
  tutorial_id: "tutorial-contract-witness",
  recipe_id: "recipe-contract-witness",
  steps: [
    {
      step_index: 1,
      standard_action: {
        step_index: 1,
        area: "upper lash line",
        goal: "define",
        product_requirement: "eyeliner",
        tool: "liner brush",
        motion: "short stroke",
        intensity: "light",
        target_result: "clean lash-line definition",
      },
      cv_standard_action: null,
      match_result: null,
      face_profile: null,
      cv_personalized_action: null,
      instructions: {},
      provenance: { recipe: "backend" },
      fallback_status: "mapping_pending",
      ar_guidance_status: "pending_cv_contract",
    },
  ],
} satisfies MyTutorialResponseDTO;
