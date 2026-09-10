import { DEMO_MODE } from "../lib/config";
export async function demo<T>(value: T): Promise<T> {
  if (!DEMO_MODE) throw new Error("生产服务尚未配置");
  return structuredClone(value);
}
