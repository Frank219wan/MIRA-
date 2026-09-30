# Week 2 frozen integration contracts

This document freezes boundaries only. It does not implement Product Matching,
My Tutorial orchestration, tutorial text generation, or AR rendering.

## Face Profile v0.3

`src.face_profile` remains the sole owner of Face Profile geometry. Backend and
frontend consumers accept version `0.3` and require its complete published
structure. Version `0.1` is a legacy fixture used only to prove rejection.
Consumers must not create a parallel geometry model or recompute CV fields.

## StandardRecipe v1

`StandardRecipe` remains unchanged: `action_units` contain `step_index`, `area`,
`goal`, `product_requirement`, `tool`, `motion`, `intensity`, and
`target_result`, plus the existing optional timing and confidence fields.

## Decoded action to CV action

`adapt_decoded_action` accepts an explicit, versioned mapping configuration. It
does exact selector matching and never guesses an A02/A04 action or numeric
baseline. Its output preserves `source_step_index`, `mapping_id`, and
`mapping_version`, alongside the CV-owned `action_id` and `parameters` shape.

`data/fixtures/decoded_cv_action_mapping_v1.json` is intentionally blocked with
`placeholder_requires_product_input`. Product/application ground truth must
approve the CV action semantics and numeric baselines before a mapping becomes
`approved`.

## Personalized Action wrapper

`PersonalizedActionWrapper` adds recipe, decoded-step, Face Profile version, and
mapping provenance. The nested CV result retains the engine fields unchanged:
`action_id`, `original_parameters`, `personalized_parameters`, `applied_rules`,
and every adjustment audit field.

## MyTutorialResponse v0.2

The response is a backend-owned orchestration schema only. It can link the
decoded action, adapted CV action, matching item, Face Profile reference,
wrapped CV result, optional user-facing instruction fields, provenance, and a
fallback status. No service currently generates this response.

AR remains `pending_cv_contract`. The frontend mock polygon, region, and vector
fields are not a production contract. CV ownership, coordinate space,
orientation/mirroring, landmarks, and confidence semantics remain unresolved.
