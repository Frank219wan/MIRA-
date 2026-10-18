# Frontend scan input guards

The backend geometry, aggregation, and personalization algorithms are unchanged.

Browser-side checks use locally served MediaPipe Tasks Vision and the existing official Face Landmarker model. No frames are sent to a third-party service. Checks run on request before countdown, during capture, and before image upload. They are not continuous real-time occlusion detection.

Initial conservative guards: minimum image edge 320px; mean grayscale below 35 or over 80% very dark pixels; mean over 240 or over 90% near-white pixels; average adjacent grayscale difference below 0.6 on a 256px thumbnail. These identify obvious unusable inputs, not calibrated facial sharpness or skin-tone quality. Face checks reject no/multiple faces, incomplete/out-of-frame geometry, very small faces, pronounced eye-line tilt/depth asymmetry, or unresolvable open eyes. They do not identify every hand, hair, glasses or other occlusion. Test with varied skin tones, lighting, devices, poses, glasses and occlusions before treating thresholds as production calibrated.

Failure stops capture/upload and gives a retry message; users can still skip scanning. Model-load failure is visible and never reported as a passed check. Tutorial illustrations are closed-eyelid schematics, not measured or generated personal results.

Sources: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js
Model: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
WASM files in public/models/face/wasm are copied from the locked @mediapipe/tasks-vision dependency; refresh them together when upgrading it.
