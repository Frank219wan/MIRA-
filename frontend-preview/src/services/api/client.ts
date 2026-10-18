import { apiConfig } from "../../lib/config";
export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  constructor(
    message: string,
    status = 0,
    code = "network_error",
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}
export async function request<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), apiConfig.timeoutMs);
  try {
    const response = await fetch(`${apiConfig.baseUrl}${path}`, {
      method: body === undefined ? "GET" : "POST",
      signal: controller.signal,
      headers:
        body === undefined || body instanceof FormData
          ? { Accept: "application/json" }
          : { Accept: "application/json", "Content-Type": "application/json" },
      ...(body === undefined
        ? {}
        : { body: body instanceof FormData ? body : JSON.stringify(body) }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok)
      throw new ApiError(
        data?.error?.message || `请求失败 (${response.status})`,
        response.status,
        data?.error?.code || "http_error",
        data?.request_id || response.headers.get("X-Request-ID") || undefined,
      );
    if (data === null)
      throw new ApiError(
        "接口未返回有效 JSON",
        response.status,
        "invalid_response",
      );
    return data as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(
      controller.signal.aborted ? "请求超时" : "无法连接后端",
      0,
      controller.signal.aborted ? "timeout" : "network_error",
    );
  } finally {
    clearTimeout(timer);
  }
}
