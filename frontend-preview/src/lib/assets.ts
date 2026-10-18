/** Resolve files copied from public/ against Vite's configured deployment base. */
export function publicAsset(path: string) {
  if (/^(?:data:|blob:|https?:\/\/)/i.test(path)) return path;
  const env = import.meta.env ?? {};
  const base = env.BASE_URL || "/";
  return `${base}${path.replace(/^\/+/, "")}`;
}
