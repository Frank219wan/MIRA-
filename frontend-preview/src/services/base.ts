import { apiConfig } from "../lib/config";
export interface ServiceStatus {
  source: "api" | "demo" | "mock-fallback" | "error";
  error?: string;
}
const statuses = new Map<string, ServiceStatus>();
export const getServiceStatus = (service: string) => statuses.get(service);
export async function withFallback<T>(
  name: string,
  live: () => Promise<T>,
  fallback: () => T | Promise<T>,
  options: { required?: boolean; demoOnly?: boolean } = {},
): Promise<T> {
  if (options.demoOnly || (apiConfig.demoMode && !options.required)) {
    statuses.set(name, { source: "demo" });
    return fallback();
  }
  try {
    const value = await live();
    statuses.set(name, { source: "api" });
    return value;
  } catch (e) {
    const error = e instanceof Error ? e.message : "服务不可用";
    statuses.set(name, {
      source: apiConfig.mockFallback && !options.required ? "mock-fallback" : "error",
      error,
    });
    if (!apiConfig.mockFallback || options.required) throw e;
    console.warn(`[MIRA ${name}] 使用参考方案：${error}`);
    return fallback();
  }
}
// Explicitly mock-only features (coach, scan quality, UI stage labels) remain available in API mode.
export async function demo<T>(value: T): Promise<T> {
  return structuredClone(value);
}
