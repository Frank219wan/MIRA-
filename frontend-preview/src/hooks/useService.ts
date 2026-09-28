import { useEffect, useState } from "react";
import { getServiceStatus } from "../services/base";
export function useService<T>(service: () => Promise<T>) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let alive = true;
    service()
      .then((v) => {
        if (alive) {
          setData(v);
          setError("");
          const status = getServiceStatus(
            (service as { statusKey?: string }).statusKey || "",
          );
          setNotice(
            status?.source === "mock-fallback"
              ? "当前服务暂不可用，正在展示演示数据。"
              : "",
          );
        }
      })
      .catch(() => {
        if (alive) setError("暂时无法读取，请刷新重试。");
      });
    return () => {
      alive = false;
    };
  }, [service]);
  return { data, error, notice };
}
