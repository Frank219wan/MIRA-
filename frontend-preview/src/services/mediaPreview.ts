import { request } from "./api/client";
import { apiConfig } from "../lib/config";

export async function uploadMediaPreview(file: File) {
  if (file.size === 0 || file.size > 100 * 1024 * 1024)
    throw new Error("请选择不超过 100 MB 的非空文件。");
  const body = new FormData();
  body.append("file", file);
  const result = await request<{ upload_id: string; preview_path: string; kind: "image" | "video" }>("/media/preview", body);
  if (!result.upload_id || result.preview_path !== `/media/preview/${result.upload_id}` || !/^\/media\/preview\/[0-9a-f]{32}\.(jpg|png|webp|mp4|mov|webm)$/.test(result.preview_path))
    throw new Error("上传未返回有效的预览地址。");
  return { uploadId: result.upload_id, url: apiConfig.baseUrl + result.preview_path, kind: result.kind };
}
