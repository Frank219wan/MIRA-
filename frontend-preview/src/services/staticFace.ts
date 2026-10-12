// Session-memory only: never write the photograph or landmarks to browser storage.
export interface StaticFace { id: string; image: string; landmarks: { x: number; y: number }[] }
let face: StaticFace | undefined;
export const getStaticFace = () => face;
export function clearStaticFace() { face = undefined; }
export async function retainStaticFace(blob: Blob, landmarks: { x: number; y: number }[]) {
  const image = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(String(reader.result));
    reader.onerror = reject; reader.readAsDataURL(blob);
  });
  face = { id: crypto.randomUUID(), image, landmarks: landmarks.map(({ x,y }) => ({ x,y })) };
}
