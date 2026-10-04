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
): Promise<T> {
  if (apiConfig.demoMode) {
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
      source: apiConfig.mockFallback ? "mock-fallback" : "error",
      error,
    });
    if (!apiConfig.mockFallback) throw e;
    console.warn(`[MIRA ${name}] 使用演示数据：${error}`);
    return fallback();
  }
}
// Explicitly mock-only features (coach, scan quality, UI stage labels) remain available in API mode.
export async function demo<T>(value: T): Promise<T> {
  return structuredClone(value);
}
