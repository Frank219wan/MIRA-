import { clearStaticFace } from "./staticFace";
import { quality, faceProfile } from "../mocks/faceProfile";
import { demo, withFallback } from "./base";
import { adaptFaceProfile } from "./adapters/face";
import type { FaceProfileDTO } from "./api/dto";
import { request, ApiError } from "./api/client";
import type { FaceScanResultDTO } from "./api/dto";
let scanRevision = 0;
let profileDTO: FaceProfileDTO | undefined;
export function setFaceProfileDTO(dto: FaceProfileDTO) {
  if (!hasFaceProfile()) throw new Error("请先同意使用面部档案");
  adaptFaceProfile(dto);
  profileDTO = structuredClone(dto);
  if (isRememberingFaceProfile()) persistProfile();
}
const PROFILE_KEY = "mira-face-profile";
export const isRememberingFaceProfile = () =>
  sessionStorage.getItem("mira-face-remember") === "true";
function persistProfile() {
  if (profileDTO)
    sessionStorage.setItem(
      PROFILE_KEY,
      JSON.stringify({
        savedAt: new Date().toISOString(),
        profile: profileDTO,
      }),
    );
}
export function setRememberFaceProfile(enabled: boolean) {
  sessionStorage.setItem("mira-face-remember", String(enabled));
  if (enabled) persistProfile();
  else sessionStorage.removeItem(PROFILE_KEY);
}
export function getFaceProfileDTO(): FaceProfileDTO | undefined {
  if (!hasFaceProfile()) return undefined;
  if (!profileDTO && isRememberingFaceProfile()) {
    try {
      const saved = JSON.parse(sessionStorage.getItem(PROFILE_KEY) || "null");
      if (saved?.profile) {
        adaptFaceProfile(saved.profile);
        profileDTO = saved.profile;
      }
    } catch {
      sessionStorage.removeItem(PROFILE_KEY);
    }
  }
  return profileDTO ? structuredClone(profileDTO) : undefined;
}
export const getFaceScanQuality = () => demo(quality);
export async function getFaceProfileContext() {
  const dto = getFaceProfileDTO();
  return dto
    ? adaptFaceProfile(dto)
    : {
        profile: await demo(faceProfile),
        provenance: { geometry: "mock", color: "mock" } as const,
        raw: undefined,
      };
}
export const getFaceProfile = async () =>
  (await getFaceProfileContext()).profile;
export const hasFaceProfile = () =>
  sessionStorage.getItem("mira-face") === "true";
export const setFaceConsent = (enabled: boolean) => {
  scanRevision++;
  if (!enabled) clearStaticFace();
  sessionStorage.setItem("mira-face", String(enabled));
  if (!enabled) {
    profileDTO = undefined;
    sessionStorage.removeItem(PROFILE_KEY);
    sessionStorage.removeItem("mira-face-remember");
  }
};

// Never replace a failed scan with a synthetic measured profile.
export async function scanFaceImages(
  images: Blob[],
): Promise<FaceScanResultDTO | null> {
  const revision = ++scanRevision;
  clearStaticFace();
  profileDTO = undefined;
  sessionStorage.removeItem(PROFILE_KEY);
  return withFallback(
    "scanFaceImages",
    async () => {
      if (!hasFaceProfile()) throw new Error("请先同意使用面部档案");
      if (images.length < 3 || images.length > 20)
        throw new Error("请选择 3–20 张图片");
      const body = new FormData();
      images.forEach((image, i) =>
        body.append("images", image, `frame-${i}.jpg`),
      );
      // Preview may be mirrored, but uploaded camera pixels are not.
      body.append("input_is_mirrored", "false");
      let result: FaceScanResultDTO;
      try {
        result = await request<FaceScanResultDTO>("/face-scan", body);
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.code === "insufficient_valid_frames"
        )
          throw new Error(
            "清晰有效的画面不足，请正对镜头、移开眼部遮挡并保持不动后重扫。",
          );
        if (error instanceof ApiError && error.code === "face_scan_unavailable")
          throw new Error(
            "扫描服务暂不可用，请稍后重试，或跳过扫描继续基础教程。",
          );
        throw error;
      }
      if (
        !Number.isInteger(result.valid_frame_count) ||
        result.valid_frame_count < 3
      )
        throw new Error("有效画面不足 3 帧，请重新采集");
      adaptFaceProfile(result.aggregated_face_profile);
      if (revision !== scanRevision || !hasFaceProfile()) return null;
      setFaceProfileDTO(result.aggregated_face_profile);
      return result;
    },
    () => null,
  );
}

export function cancelPendingFaceScan() {
  scanRevision++;
}
