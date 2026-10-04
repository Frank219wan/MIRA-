import { quality, faceProfile } from "../mocks/faceProfile";
import { demo, withFallback } from "./base";
import { adaptFaceProfile } from "./adapters/face";
import type { FaceProfileDTO } from "./api/dto";
import { request } from "./api/client";
import type { FaceScanResultDTO } from "./api/dto";
let scanRevision = 0;
let profileDTO: FaceProfileDTO | undefined;
export function setFaceProfileDTO(dto: FaceProfileDTO) {
  if (!hasFaceProfile()) throw new Error("请先同意使用面部档案");
  adaptFaceProfile(dto);
  profileDTO = structuredClone(dto);
}
export const getFaceProfileDTO = () =>
  hasFaceProfile() && profileDTO ? structuredClone(profileDTO) : undefined;
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
  sessionStorage.setItem("mira-face", String(enabled));
  if (!enabled) profileDTO = undefined;
};

// Never replace a failed scan with a synthetic measured profile.
export async function scanFaceImages(
  images: Blob[],
): Promise<FaceScanResultDTO | null> {
  const revision = ++scanRevision;
  profileDTO = undefined;
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
      const result = await request<FaceScanResultDTO>("/face-scan", body);
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
