import { quality, faceProfile } from "../mocks/faceProfile";
import { demo } from "./base";
import { adaptFaceProfile } from "./adapters/face";
import type { FaceProfileDTO } from "./api/dto";
// No face-scan HTTP route exists yet. CV integration supplies its v0.1 output here.
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
  sessionStorage.setItem("mira-face", String(enabled));
  if (!enabled) profileDTO = undefined;
};
