// Conservative input guards, not calibrated measures of scan accuracy.
export function pixelIssue(
  width: number,
  height: number,
  pixels: Uint8ClampedArray,
): string | null {
  if (Math.min(width, height) < 320)
    return "图片分辨率过低，请使用更清晰的原图重拍。";
  let mean = 0,
    dark = 0,
    bright = 0,
    edge = 0;
  const count = pixels.length / 4;
  for (let i = 0; i < pixels.length; i += 4) {
    const v = (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3;
    mean += v;
    if (v < 20) dark++;
    if (v > 245) bright++;
    if (i >= 4)
      edge += Math.abs(v - (pixels[i - 4] + pixels[i - 3] + pixels[i - 2]) / 3);
  }
  if (!count || mean / count < 35 || dark / count > 0.8)
    return "画面过暗，请面向均匀光源后重拍。";
  if (mean / count > 240 || bright / count > 0.9)
    return "画面过亮，请避开强光后重拍。";
  if (edge / count < 0.6) return "画面缺少清晰细节，请擦净镜头、对焦后重拍。";
  return null;
}
export type Point = { x: number; y: number; z: number };
export function faceIssue(faces: Point[][]): string | null {
  if (!faces.length) return "未能识别人脸，请正对镜头，移开面部遮挡后重试。";
  if (faces.length !== 1) return "画面中有多张脸，请只保留你自己。";
  const p = faces[0];
  if (p.length < 468 || p.some((q) => !Number.isFinite(q.x + q.y + q.z)))
    return "眼部信息不完整，请移开遮挡后重试。";
  const xs = p.map((q) => q.x),
    ys = p.map((q) => q.y);
  if (
    Math.min(...xs) < 0.02 ||
    Math.max(...xs) > 0.98 ||
    Math.min(...ys) < 0.02 ||
    Math.max(...ys) > 0.98
  )
    return "面部未完整入镜，请稍微远离镜头。";
  if (Math.max(...xs) - Math.min(...xs) < 0.2)
    return "面部距离较远，请靠近一些。";
  const left = p[33],
    right = p[263],
    span = Math.abs(right.x - left.x);
  if (
    span < 0.06 ||
    Math.abs(right.y - left.y) / span > 0.22 ||
    Math.abs(right.z - left.z) / span > 0.45
  )
    return "请将头部摆正，正对镜头后重试。";
  if (
    Math.abs(p[159].y - p[145].y) / span < 0.025 ||
    Math.abs(p[386].y - p[374].y) / span < 0.025
  )
    return "无法清楚识别睁开的双眼，请睁眼并移开眼部遮挡后重试。";
  return null;
}
let detector:
  Promise<import("@mediapipe/tasks-vision").FaceLandmarker> | undefined;
export async function checkScanImage(
  source: HTMLVideoElement | ImageBitmap,
): Promise<Point[]> {
  const width =
    source instanceof HTMLVideoElement ? source.videoWidth : source.width;
  const height =
    source instanceof HTMLVideoElement ? source.videoHeight : source.height;
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = Math.max(1, Math.round((256 * height) / width));
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  const issue = pixelIssue(
    width,
    height,
    ctx.getImageData(0, 0, canvas.width, canvas.height).data,
  );
  if (issue) throw new Error(issue);
  if (!detector)
    detector = import("@mediapipe/tasks-vision")
      .then(async ({ FaceLandmarker, FilesetResolver }) =>
        FaceLandmarker.createFromOptions(
          await FilesetResolver.forVisionTasks("/models/face/wasm"),
          {
            baseOptions: {
              modelAssetPath: "/models/face/face_landmarker.task",
              delegate: "CPU",
            },
            runningMode: "IMAGE",
            numFaces: 2,
          },
        ),
      )
      .catch((e) => {
        detector = undefined;
        throw e;
      });
  let model;
  try {
    model = await detector;
  } catch {
    throw new Error("取景检查暂不可用，请重试或跳过扫描。");
  }
  const faces = model.detect(canvas).faceLandmarks;
  const problem = faceIssue(faces);
  if (problem) throw new Error(problem);
  return faces[0];
}
export async function checkScanUploads(images: Blob[]): Promise<void> {
  if (images.length < 3 || images.length > 20)
    throw new Error("请选择 3–20 张正面照片。");
  for (let i = 0; i < images.length; i++) {
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(images[i]);
    } catch {
      throw new Error(`第 ${i + 1} 张图片无法读取，请换一张照片。`);
    }
    try {
      await checkScanImage(bitmap);
    } catch (e) {
      throw new Error(
        `第 ${i + 1} 张：${e instanceof Error ? e.message : "请重新拍摄。"}`,
      );
    } finally {
      bitmap.close();
    }
  }
}

// Compare against both the initial pose and the preceding sample in the caller.
// Relative to eye span, so the guard does not depend on camera resolution.
export function motionIssue(before: Point[], after: Point[]): string | null {
  const span = Math.hypot(
    before[263].x - before[33].x,
    before[263].y - before[33].y,
  );
  const newSpan = Math.hypot(
    after[263].x - after[33].x,
    after[263].y - after[33].y,
  );
  const movement =
    [1, 33, 263, 168].reduce(
      (sum, i) =>
        sum + Math.hypot(after[i].x - before[i].x, after[i].y - before[i].y),
      0,
    ) / 4;
  const tilt = Math.atan2(
    before[263].y - before[33].y,
    before[263].x - before[33].x,
  );
  const newTilt = Math.atan2(
    after[263].y - after[33].y,
    after[263].x - after[33].x,
  );
  const turn = Math.abs(
    after[263].z - after[33].z - (before[263].z - before[33].z),
  );
  if (
    span <= 0 ||
    movement / span > 0.1 ||
    Math.abs(newSpan / span - 1) > 0.18 ||
    Math.abs(newTilt - tilt) > 0.16 ||
    turn / span > 0.16
  )
    return "检测到面部移动，本次采集已停止。请保持头部和手机不动，重新开始。";
  return null;
}

// Give a blink or brief tracking jitter time to settle; never accept a failing frame.
export async function tolerateBriefScanChange<T>(
  check: () => Promise<T>,
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await check();
    } catch (error) {
      if (
        attempt >= 4 ||
        !(error instanceof Error) ||
        !/面部移动|睁开的双眼/.test(error.message)
      )
        throw error;
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
  }
}
