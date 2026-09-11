# Beauty Face Engine — Week 1 CV

一个基于 Python、OpenCV 和 **MediaPipe Tasks API Face Landmarker** 的人脸关键点与连续眼部几何原型。当前版本处理单张正脸自拍，检测最多一张人脸，并输出眼部/眉眼测量验证图和结构化几何 JSON。

## 项目结构

```text
beauty-face-engine/
├── src/
│   ├── __init__.py
│   ├── face_landmarker.py        # MediaPipe 推理与通用图片 I/O
│   ├── eye_landmarks.py          # 眼部点提取、debug 图和 JSON pipeline
│   ├── face_geometry.py          # 与 MediaPipe 解耦的纯二维几何
│   ├── face_profile.py           # 面向个性化引擎的稳定输出契约
│   └── batch_analyze.py          # 多图片分析与 CSV 汇总
├── tests/
│   ├── test_face_landmarker.py
│   ├── test_eye_landmarks.py
│   ├── test_face_geometry.py
│   ├── test_face_profile.py
│   └── test_batch_analyze.py
├── data/
│   ├── input/
│   │   └── selfie.jpg            # 需要提供
│   └── output/
│       ├── landmarks_result.jpg      # 第一阶段输出
│       ├── eye_landmarks_result.jpg  # 眼轴、眼高和眉眼测量验证图
│       ├── face_geometry.json        # 单图片连续眼部几何输出
│       ├── face_profile.json         # 个性化算法输入契约
│       ├── face_summary.csv          # 多图片关键指标汇总
│       └── batch/                    # 每张图片的 JSON/debug 输出
├── models/
│   └── face_landmarker.task      # MediaPipe 模型（本工作区已下载）
├── requirements.txt
└── README.md
```

## 环境准备

建议使用 Python 3.9–3.12。在项目目录中创建并激活虚拟环境：

```bash
cd beauty-face-engine
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell 使用：

```powershell
.venv\Scripts\Activate.ps1
```

安装依赖：

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` 在 macOS 上暂时固定 MediaPipe 0.10.21，以规避 MediaPipe
1.0.x 的 CPU Face Landmarker 原生崩溃；其他平台使用 1.0.1。业务代码在两者上均使用
Tasks API，不使用旧版 `solutions.face_mesh`。

## 准备模型和图片

本工作区已经在下列位置准备好官方模型。如果文件不存在（例如从 Git 重新克隆后），请从 [MediaPipe Face Landmarker 官方页面](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/index#models) 下载 Face Landmarker 模型包。

1. 下载 Face Landmarker 模型包。
2. 将模型重命名或保存为：

   ```text
   models/face_landmarker.task
   ```

3. 将一张光线充足、无遮挡、正对镜头的自拍 JPG 保存为：

   ```text
   data/input/selfie.jpg
   ```

请不要将真实自拍或其他个人数据提交到 Git 仓库；本项目的 `.gitignore` 已默认忽略输入、输出、模型和虚拟环境。

## 运行

第一阶段全部 478 点验证仍可单独运行：

```bash
python src/face_landmarker.py
```

眼部提取与几何计算：

```bash
python src/eye_landmarks.py
```

默认行为：

- 输入：`data/input/selfie.jpg`
- 模型：`models/face_landmarker.task`
- debug 图：`data/output/eye_landmarks_result.jpg`
- JSON：`data/output/face_geometry.json`、`data/output/face_profile.json`
- 终端打印眼宽、眼高、眼距、眼尾角、眉眼距离和左右差异
- 未检测到人脸、模型缺失或图片不可读时，会打印明确错误并以非零状态退出

批量分析 `data/input/*.jpg`：

```bash
python src/batch_analyze.py
```

每张图片会在 `data/output/batch/` 下生成 `<原文件名>_geometry.json`
和对应 debug 图，汇总指标写入 `data/output/face_summary.csv`。单张图片检测失败时，
该 JSON 会记录 `face_detected: false` 和错误信息，CSV 对应行的指标留空并填写
`error`；其余图片仍会继续处理。

如果保存下来的自拍已经被水平镜像，必须显式传入：

```bash
python src/eye_landmarks.py --mirrored-input
```

程序不会根据画面内容猜测是否镜像。默认输入为未镜像图片；此时人物本人的左眼通常位于图片右侧。`--mirrored-input` 会交换两个 MediaPipe 眼部组，使 JSON 中的 `left` / `right` 仍表示人物本人。

## 眼部关键点和公式

未镜像输入使用：

- 人物左眼：inner `362`、outer `263`、upper `386`、lower `374`
- 人物右眼：inner `133`、outer `33`、upper `159`、lower `145`

所有 pixel distance 都使用二维 Euclidean distance：

- eye width = `distance(inner_corner, outer_corner)`
- eye height = `distance(upper_lid, lower_lid)`
- eye aspect ratio = `eye_height / eye_width`
- inner eye distance = `distance(left_inner_corner, right_inner_corner)`
- mean eye width = `(left_eye_width + right_eye_width) / 2`
- eye spacing ratio = `inner_eye_distance / mean_eye_width`

Eye Height 会受到眨眼影响；当前阶段只计算，不做补偿或分类。

眉毛参考使用 MediaPipe Tasks 官方连接定义中靠眼睛一侧的五点轮廓：人物左眉
`276, 283, 282, 295, 285`，人物右眉 `46, 53, 52, 65, 55`。眉眼距离定义为
这五点质心到 inner–outer 眼轴所在直线的垂直距离，因此比单点和原始 y 差更能抵抗
单点抖动及轻微画面内旋转；对应 ratio 再除以同侧眼宽。

- eye tail angle = `degrees(atan2(inner_y - outer_y, abs(outer_x - inner_x)))`
- positive angle = 人物眼尾高于内眼角（图像坐标 y 轴向下，故对 y 差取反）
- size asymmetry = `abs(left - right) / mean(left, right)`
- angle difference = `abs(left_angle - right_angle)`

## 测试

```bash
python -m unittest discover -s tests -v
```

## 模块设计

- `FaceLandmarkerDetector`：负责配置和调用 MediaPipe Tasks Face Landmarker。
- `eye_landmarks.py`：复制 8 个眼部点和两个五点眉毛轮廓，不修改原始 MediaPipe 结果。
- `face_geometry.py`：只接收二维点，使用 Euclidean distance，不依赖 MediaPipe/OpenCV。

当前版本只输出连续几何量，不包含眼型/眼距/眼尾分类、Face Profile 标签、AR、美妆推荐、个性化规则或 LLM。

## Week 1 后端更新

- 后端以 FastAPI + SQLite 提供教程解析、Recipe 查询、Beauty Kit、Matching、CV Adaptation 与 Explanation 的稳定接口。
- 教程解析器当前使用离线 `MockTutorialVisionProvider`，将视频/帧目录引用转换为经校验的五步骤 `StandardRecipe`；真实视频理解 Provider 尚未接入。
- CV 的 `Face Profile v0.1` 仍由 `src/face_profile.py` 维护；后端只校验并原样消费，不增加脸型或美学判断。
- Matching、CV Adaptation 与 Explanation 当前均为结构性占位，不包含匹配算法、个性化或外部 LLM 调用。
- 详细的本地运行、接口、调试、Replay 与限制说明见 [Week 1 后端文档](docs/week1_backend.md)。

## Pipeline Architecture

```text
Image
  ↓
Face Landmark
  ↓
Eye Landmark Extraction
  ↓
Face Geometry
  ↓
Face Profile
  ↓
Personalization Engine (Next Stage)
```

`Face Profile` 是几何层与下一阶段之间的稳定数据契约，只重新组织已计算的连续参数，
不重复几何计算，也不生成眼型、眼距或美学分类。

## Current Limitations

- 尚未进行 head pose normalization。
- Eye tail angle 可能受到 yaw、pitch 和 roll 影响。
- Eye height 可能受到眨眼和其他面部表情影响。
- Brow landmarks 可能受到头发、妆容或其他遮挡影响。

## Output Files

- `landmarks_result.jpg`：全部 478 个 face landmarks 的检测验证图。
- `eye_landmarks_result.jpg`：眼部关键点、眼轴和眉眼测量 debug 图。
- `face_geometry.json`：包含 landmarks 坐标与测量过程的底层几何数据。
- `face_profile.json`：供后续 Personalization Engine 使用的连续参数契约。
