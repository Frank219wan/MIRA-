// Short-lived copy of the current review frame; never persisted or sent to an API.
let preview: string | undefined;
export function getPreferencePreview() {
  return preview;
}
export function clearPreferencePreview() {
  preview = undefined;
}
export async function copyPreferencePreview(source?: string) {
  clearPreferencePreview();
  if (source?.startsWith("blob:")) {
    try {
      const blob = await (await fetch(source)).blob();
      preview = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch {
      /* use the existing scan guide */
    }
  }
}
