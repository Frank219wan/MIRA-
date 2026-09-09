import unittest
from types import SimpleNamespace

from src.face_landmarker import (
    FaceLandmarkerError,
    require_first_face_landmarks,
)


class FaceLandmarkerTests(unittest.TestCase):
    def test_no_face_raises_clear_error(self):
        result = SimpleNamespace(face_landmarks=[])
        with self.assertRaisesRegex(FaceLandmarkerError, "未检测到人脸"):
            require_first_face_landmarks(result)


if __name__ == "__main__":
    unittest.main()
