import { quality, faceProfile } from "../mocks/faceProfile";
import { demo } from "./base";
export const getFaceScanQuality = () => demo(quality);
export const getFaceProfile = () => demo(faceProfile);
export const hasFaceProfile = () =>
  sessionStorage.getItem("mira-face") === "true";
export const setFaceConsent = (enabled: boolean) => {
  sessionStorage.setItem("mira-face", String(enabled));
};
