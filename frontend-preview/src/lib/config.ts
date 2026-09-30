const env = import.meta.env ?? {};
const timeout = Number(env.VITE_API_TIMEOUT_MS ?? 30000);
export const apiConfig = {
  demoMode: env.VITE_DEMO_MODE !== "false",
  mockFallback: env.VITE_MOCK_FALLBACK !== "false",
  baseUrl: (env.VITE_API_BASE_URL || "/api").replace(/\/$/, ""),
  timeoutMs: Number.isFinite(timeout) && timeout > 0 ? timeout : 30000,
  exampleMediaPath: env.VITE_EXAMPLE_MEDIA_PATH || "",
  exampleMediaKind:
    env.VITE_EXAMPLE_MEDIA_KIND === "frame_directory"
      ? ("frame_directory" as const)
      : ("video" as const),
};
export const DEMO_MODE = apiConfig.demoMode;
