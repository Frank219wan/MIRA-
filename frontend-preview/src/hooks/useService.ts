import { useEffect, useState } from "react";
export function useService<T>(service: () => Promise<T>) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    service()
      .then((v) => {
        if (alive) setData(v);
      })
      .catch(() => {
        if (alive) setError("暂时无法读取，请刷新重试。");
      });
    return () => {
      alive = false;
    };
  }, [service]);
  return { data, error };
}
