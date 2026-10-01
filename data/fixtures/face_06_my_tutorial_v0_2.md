# Face 06 — My Tutorial v0.2

## A04 · Step 5

- **Where:** upper lash line
- **How:** 让线条更平一些（5.781666 → 3.971266，Δ -1.8104）；向外延伸得更远一些（0.34493 → 0.38178899654，Δ 0.03685899654）；保持 start_position_ratio 不变（0.985925 → 0.985925，Δ 0.0）
- **Why:** 依据 CV 证据：eye_tail_angle.mean=11.635，规则 R02；relative_eye_length.mean=0.1898，规则 R03。触发规则：R02,R03。
- **Stop when:** clean lash-line definition
- **Applied rules:** R02, R03
- **Reference parameters:** `{"reference_direction_deg": 5.781666, "reference_extension_ratio": 0.34493, "start_position_ratio": 0.985925}`
- **Personalized parameters:** `{"personalized_direction_deg": 3.971266, "personalized_extension_ratio": 0.38178899654, "start_position_ratio": 0.985925}`
- **Provenance:** `data/fixtures/main_demo/face_06_personalization.json` + `data/fixtures/main_demo/main_demo_reference.json` via adapter v1.0 and deterministic template v1.0.

## Known blocker

A02 was normalized successfully, but no committed decoded StandardRecipe action identifies its user-facing area, tool, motion, intensity, or target result. No A02 tutorial wording is fabricated in this artifact.
