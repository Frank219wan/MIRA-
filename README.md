# MIRA Vision Engine — Face Profile v0.3 + Personalization Engine v0

一个基于 Python、OpenCV 和 **MediaPipe Tasks API Face Landmarker** 的人脸关键点与连续眼部几何原型。当前 CV 版本处理单张正脸自拍，检测最多一张人脸，并输出眼部/眉眼测量验证图、结构化几何 JSON 和 Face Profile v0.3。v0.3 保留 v0.2 的 R01–R10 连续几何输入契约，并增加二维 face-roll normalization。

Personalization Engine v0 在 Face Profile v0.3 之后独立运行。第一阶段以确定性数值规则为同一份 Cat Eye Standard Makeup Action 调整 A04 eyeliner 与 A02 lower eyelid 参数，只启用 R01–R06。CV pipeline 不依赖个性化模块；个性化模块也不运行 landmark inference。两个模块都不生成眼型分类或美学标签。

## 项目结构

```text
beauty-face-engine/
├── src/
│   ├── __init__.py
│   ├── face_landmarker.py        # MediaPipe 推理与通用图片 I/O
│   ├── eye_landmarks.py          # 眼部点提取、debug 图和 JSON pipeline
│   ├── face_geometry.py          # 与 MediaPipe 解耦的纯二维几何
│   ├── pose_normalization.py     # 二维 face-roll 估计与坐标旋转
│   ├── face_profile.py           # 面向个性化引擎的稳定输出契约
│   ├── batch_analyze.py          # 多图片分析与 CSV 汇总
│   ├── repeatability_analysis.py # 同一人物多照片的重复性统计
│   ├── makeup_rules.py           # R01–R10 registry 与连续规则映射
│   ├── personalization_engine.py # 输入校验、规则执行与输出组装
│   ├── new_input_validation.py   # 新真人输入的连续个体差异验证
│   ├── reference_action_geometry.py  # 局部教程标注点的纯几何
│   ├── reference_action_annotator.py # 局部教程人工点击及 debug overlay
│   ├── reference_action_adapter.py   # 参考几何转换为 A04 baseline
│   ├── reference_relative_personalization.py # Absolute/Reference-Relative wrapper
│   ├── eye_local_profile.py      # 教程/用户共用的单眼局部几何契约
│   └── eye_local_profile_dataset.py # reference 与 face_05–11 验证产物
├── tests/
│   ├── test_face_landmarker.py
│   ├── test_eye_landmarks.py
│   ├── test_face_geometry.py
│   ├── test_pose_normalization.py
│   ├── test_face_profile.py
│   ├── test_batch_analyze.py
│   ├── test_repeatability_analysis.py
│   ├── test_makeup_rules.py
│   ├── test_personalization_engine.py
│   ├── test_new_input_validation.py
│   ├── test_reference_action_geometry.py
│   ├── test_reference_action_annotator.py
│   ├── test_reference_action_adapter.py
│   ├── test_reference_relative_personalization.py
│   └── test_eye_local_profile.py
├── examples/
│   ├── cat_eye_standard_recipe.json # A04 + A02 人工 baseline/fallback
│   └── reference/             # 放置局部教程图，不提交真人素材
├── data/
│   ├── input/
│   │   └── selfie.jpg            # 需要提供
│   └── output/
│       ├── landmarks_result.jpg      # 第一阶段输出
│       ├── eye_landmarks_result.jpg  # 眼轴、眼高和眉眼测量验证图
│       ├── face_geometry.json        # 单图片连续眼部几何输出
│       ├── face_profile.json         # 个性化算法输入契约
│       ├── face_summary.csv          # 多图片关键指标汇总
│       ├── repeatability_report.json      # 保留的 v0.2 baseline
│       ├── repeatability_report_v0.3.json # v0.3 重复性与 before/after
│       ├── repeatability_report_v0.3.csv  # v0.3 汇总与逐图原始值
│       ├── batch/                    # 每张图片的 JSON/debug 输出
│       └── repeatability_v0.3/       # v0.3 逐图 JSON/profile/debug
├── models/
│   └── face_landmarker.task      # MediaPipe 模型（本工作区已下载）
├── requirements.txt
└── README.md
```

## 环境准备

建议使用 Python 3.10–3.12（当前 API/contract 模块使用运行时 `str | None` 类型注解）。在项目目录中创建并激活虚拟环境：

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
- 终端打印眼宽、眼高、眼距、眼尾角、相对眼长、眼宽高比、下眼睑空间、内眼角角度、眉眼距离和左右差异
- 未检测到人脸、模型缺失或图片不可读时，会打印明确错误并以非零状态退出

批量分析 `data/input/*.jpg`：

```bash
python src/batch_analyze.py
```

每张图片会在 `data/output/batch/` 下生成 `<原文件名>_geometry.json`
和对应 debug 图，汇总指标写入 `data/output/face_summary.csv`。单张图片检测失败时，
该 JSON 会记录 `face_detected: false` 和错误信息，CSV 对应行的指标留空并填写
`error`；其余图片仍会继续处理。

同一人物多照片重复性分析会优先发现 `data/input/repeat_*.jpg`，扩展名匹配不区分
大小写：

```bash
python src/repeatability_analysis.py
```

也可以手动指定至少两张图片：

```bash
python src/repeatability_analysis.py --images data/input/a.jpg data/input/b.jpg
```

工具逐张调用现有 Face Landmarker → Face Geometry → Face Profile v0.3 pipeline，
不会重新实现或修改几何公式。它分析 `eye_tail_angle.mean`、
`relative_eye_length.mean`、`brow_eye_ratio.mean`、
`lower_lid_space_ratio.mean` 和 `inner_corner_angle.mean_deg`，输出每个指标的
`n/mean/std/min/max/range/cv`。`std` 使用样本标准差（`n-1`），
`cv = std / abs(mean)`；当绝对 mean 不大于 `1e-9` 时，CV 写为 JSON `null` 和
CSV 空值。每张照片的原始值、检测状态和 debug 路径都会保留，超过 2 个样本标准差
的值只标记为人工检查，不会自动删除。

默认读取 `data/output/repeatability_report.json` 作为 v0.2 baseline，并将
`before_std/after_std`、`before_cv/after_cv` 写入
`data/output/repeatability_report_v0.3.json`。如果 baseline 不存在，v0.3 测量仍会
完成，并在报告中将 comparison 标记为 unavailable。

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

### Face Profile v0.2 引入、v0.3 保留的连续特征

MediaPipe landmark 语义以官方 Tasks API 的
[FaceLandmarksConnections](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/web/vision/face_landmarker/face_landmarks_connections.ts)
和同文件中的官方 face tessellation 为准。

#### Relative Eye Length

face width 使用官方 `FACE_LANDMARKS_FACE_OVAL` 中的两个侧向轮廓点 `234` 和
`454`。官方连接分别包含 `93–234–127` 与 `356–454–323`，因此这里仅将两点解释为
左右侧向 face-oval reference，不赋予颧骨或其他解剖标签。

- `face_width_px = distance(landmark_234, landmark_454)`
- `relative_eye_length_left = left_eye_width_px / face_width_px`
- `relative_eye_length_right = right_eye_width_px / face_width_px`
- `relative_eye_length_mean = mean(left, right)`
- `eye_width_height_ratio = eye_width_px / eye_height_px`

`relative_eye_length` 是 R03/R04 的主指标。它消除整体等比例缩放的直接影响，但仍会
受 yaw、透视、镜头畸变和侧向轮廓定位影响。`eye_width_height_ratio` 是辅助指标，且会
随眨眼、眯眼和表情变化。

#### Lower Lid Space Ratio

每只眼使用三个官方 tessellation 直连边。人物左眼为
`373–254, 374–253, 380–252`；人物右眼为
`144–24, 145–23, 153–22`。每组第一点属于官方 lower-eye contour，第二点是与其
直接相连的下方网格 reference。

- `lower_lid_space_px = mean(distance(lower_lid_i, infraorbital_i))`
- `lower_lid_space_ratio = lower_lid_space_px / same_side_eye_width_px`

JSON 同时保留三个 segment pixel distance、平均 pixel measurement 和 normalized
ratio。该指标是二维 lower-lid-to-infraorbital mesh gap，会受 pitch、yaw、眯眼、笑容、
下眼睑张力、遮挡和 landmark 抖动影响；它不是解剖深度或真实面积。

#### Inner Corner Angle

角度以 inner corner 为顶点，使用官方眼轮廓中与顶点直接相邻的 upper-inner 和
lower-inner 点：

- 人物左眼：vertex `362`，upper-inner `398`，lower-inner `382`
- 人物右眼：vertex `133`，upper-inner `173`，lower-inner `155`
- `angle = acos(dot(v_upper, v_lower) / (|v_upper| * |v_lower|))`

输出范围为有限的 `(0, 180]` 度连续值。它会受分辨率、眼睑开合、内眼角遮挡、妆容、
表情和 head pose 影响，不生成 round、sharp 或其他标签。

眉毛参考使用 MediaPipe Tasks 官方连接定义中靠眼睛一侧的五点轮廓：人物左眉
`276, 283, 282, 295, 285`，人物右眉 `46, 53, 52, 65, 55`。眉眼距离定义为
这五点质心到 inner–outer 眼轴所在直线的垂直距离，因此比单点和原始 y 差更能抵抗
单点抖动及轻微画面内旋转；对应 ratio 再除以同侧眼宽。

在 Face Profile v0.2/v0.3 中，`brow_eye_ratio` 的规则语义是 **Upper Blending Space
Proxy**：它表示眉眼之间的相对空间，不是 visible upper eyelid area，也不能直接用于
判断 hooded eye。v0.3 不修改该指标的既有公式。

- eye tail angle = `degrees(atan2(inner_y - outer_y, abs(outer_x - inner_x)))`
- positive angle = 人物眼尾高于内眼角（图像坐标 y 轴向下，故对 y 差取反）
- size asymmetry = `abs(left - right) / mean(left, right)`
- angle difference = `abs(left_angle - right_angle)`

## Pose normalization

Face Profile v0.3 在 pixel coordinate 中进行轻量级二维 roll normalization。每只眼的
center 使用既有 inner/outer corner 的中点：人物左眼 `362, 263`，人物右眼
`133, 33`。为了同时兼容镜像和非镜像输入，两个 eye center 按图像 x 坐标排序为
screen-left 与 screen-right：

```text
roll_angle = atan2(y_screen_right - y_screen_left,
                   x_screen_right - x_screen_left)
face_center = mean(left_eye_center, right_eye_center)
normalized_point = rotate(original_point, face_center, -roll_angle)
```

所有已选 geometry landmarks 使用同一旋转矩阵。既有 `normalized` 和 `pixel` 坐标保持
原样，每个 landmark 另外保存 `pose_normalized` 与 `pose_normalized_pixel`。既有
feature 字段改为消费 roll-normalized 坐标，但 landmark index、公式目标与 R01–R10
字段路径不变。`face_geometry.json` 保存 `pose_normalization.roll_angle_deg`、旋转中心、
参考 index 和 `applied`；Face Profile 的 `confidence.pose_normalized` 与 `applied`
保持一致。旧 geometry JSON 缺少 normalization metadata 时仍可构建 v0.3 profile，
此时该 confidence 为 `false`。

当前 normalization 只补偿图像平面内的 roll。yaw、pitch、镜头透视、表情和 landmark
定位变化仍可能造成 feature 波动。左右眼 center 的真实垂直不对称也可能被 roll 估计
吸收，因此 roll angle 是二维技术校正量，不是三维 head-pose measurement。

## Personalization Engine v0

### 架构与输入契约

`makeup_rules.py` 保存规则 registry、校准参数和不依赖 I/O 的纯数值函数；
`personalization_engine.py` 负责 Face Profile/action schema 校验、选择规则、深拷贝原始参数、
组装结果和严格 JSON 输出。规则不调用 CV，也不让 LLM 生成数值。

单 action 输入为：

```json
{
  "face_profile": {
    "version": "0.3",
    "eye_geometry": {
      "eye_tail_angle": {"mean": 10.386},
      "relative_eye_length": {"mean": 0.2145},
      "lower_lid_space_ratio": {"mean": 0.1379}
    }
  },
  "standard_makeup_action": {
    "action_id": "A04",
    "parameters": {
      "direction_angle_deg": 10.0,
      "extension_factor": 1.0
    }
  },
  "target_effect": "cat_eye"
}
```

运行：

```bash
python src/personalization_engine.py \
  --input data/input/personalization_request.json \
  --output data/output/personalized_action.json
```

输出保留输入 action 的完整参数副本，并附带规则审计信息：

```json
{
  "action_id": "A04",
  "original_parameters": {
    "direction_angle_deg": 10.0,
    "extension_factor": 1.0
  },
  "personalized_parameters": {
    "direction_angle_deg": 11.8456,
    "extension_factor": 0.972333
  },
  "applied_rules": ["R01", "R02", "R03", "R04"],
  "adjustments": [
    {
      "rule_ids": ["R01", "R02"],
      "feature_path": "eye_geometry.eye_tail_angle.mean",
      "feature_value": 10.386,
      "parameter": "direction_angle_deg",
      "operation": "add",
      "adjustment_value": 1.8456,
      "original_value": 10.0,
      "personalized_value": 11.8456
    },
    {
      "rule_ids": ["R03", "R04"],
      "feature_path": "eye_geometry.relative_eye_length.mean",
      "feature_value": 0.2145,
      "parameter": "extension_factor",
      "operation": "multiply",
      "adjustment_value": 0.972333,
      "original_value": 1.0,
      "personalized_value": 0.972333
    }
  ]
}
```

`personalize_recipe()` 复用同一个单 action executor，可一次处理
`examples/cat_eye_standard_recipe.json` 中的 A04 和 A02；每个 action 仍使用上面的输出 schema。

### R01–R06 连续规则

所有规则采用同一个 clamped linear mapping：

```text
t = clamp((feature - feature_low) / (feature_high - feature_low), 0, 1)
mapped = output_at_low + t * (output_at_high - output_at_low)
```

| Rules | Face Profile 输入 | Action 参数 | v0 provisional calibration |
|---|---|---|---|
| R01/R02 | `eye_tail_angle.mean` | A04 `direction_angle_deg` | 0°→+6° correction，15°→+0° correction；加到 standard action |
| R03/R04 | `relative_eye_length.mean` | A04 `extension_factor` | 0.17→×1.18，0.23→×0.90 |
| R05 | `lower_lid_space_ratio.mean` | A02 `range_factor` | 0.12→×0.80，0.18→×1.10 |
| R06 | `lower_lid_space_ratio.mean` | A02 `intensity_factor` | 0.12→×0.85，0.18→×1.05 |

区间外只钳制到端点，不外推。anchor 是待产品验证的工程校准参数，不是分类 threshold，
也不表示“标准脸”。R03/R04 只消费 normalized ratio，不使用 pixel length。

### Rule registry 范围

| Rules | Status | 当前执行 |
|---|---|---|
| R01–R06 | `active` | 是 |
| R07/R08 | `validation_only` | 否 |
| R09/R10 | `candidate` | 否 |

R07–R10 只在 registry 中登记，Personalization Engine v0 不会把它们加入
`applied_rules`，也不会修改其目标参数。

### 三人 Demo Validation

使用现有真人输入 `face_01.jpg`、`face_03.jpg`、`face_06.jpg`，分别通过原有 v0.3
pipeline 生成 Person A/B/C profile，再应用同一份
`cat_eye_standard_recipe.json`（A04 direction `10.0°`、extension `1.0`、
`target_region="outer_third"`；A02 range
`1.0`、intensity `1.0`）。三张图片都成功检测到一张脸。

| Person | tail angle mean | relative eye length | lower-lid ratio | direction | extension | lower-lid range | lower-lid intensity | Applied rules |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A | 10.386° | 0.2145 | 0.1379 | 11.8456° | 0.972333 | 0.8895 | 0.909667 | R01–R06 |
| B | 2.331° | 0.2156 | 0.1371 | 15.0676° | 0.9672 | 0.8855 | 0.907 | R01–R06 |
| C | 11.635° | 0.1898 | 0.1697 | 11.346° | 1.0876 | 1.0485 | 1.015667 | R01–R06 |

完整审计输出写入 `data/output/personalization_demo/personalization_demo.json`，扁平对比
写入同目录的 `personalization_comparison.csv`。输出目录默认被 `.gitignore` 忽略，避免
提交真人衍生数据。

## 新真人输入连续差异验证

`new_input_validation.py` 优先发现文件名大小写不敏感的 `new_*.jpg/JPG/png`。没有按此
命名时，可以显式传入图片；两种方式都会逐张复用原有 Face Landmarker → Geometry →
Face Profile v0.3 pipeline，再把成功 profile 送入现有 Personalization Engine v0：

```bash
python src/new_input_validation.py

python src/new_input_validation.py --images \
  data/input/person_a.jpg data/input/person_b.png
```

固定输出根目录为 `data/output/new_input_validation/`：

- `individual_profiles/`：逐图 geometry、Face Profile 和 debug 图；
- `individual_personalization/`：逐人的完整 recipe 个性化结果；
- `new_input_face_comparison.csv`：每行一个输入，包含五个连续 Face Profile 指标；
- `new_input_personalization_comparison.csv`：每行一个输入，包含 A04/A02 参数、rule group
  和每个参数相对 standard recipe 的 `increase/decrease/unchanged`；
- `new_input_validation.json`：检测计数、逐人结果、feature min/max/range，以及逐对绝对差。

检测失败的图片仍保留一行和明确错误，指标保持空值；不会从局部眼图补算、删除样本或
人为放大差异。该报告只验证 continuous personalization sensitivity，不创建 eye type
label，也不把临时 calibration 解释为美妆科学结论。

## Rule Calibration Dataset（Demo 样本）

`rule_calibration_dataset.py` 精确检查 `data/input/face_01`–`face_11`，按实际文件扩展名
匹配 JPG/JPEG/PNG；逐张复用既有 Face Profile v0.3 pipeline，仅整理成功样本的连续
指标和当前 RuleCalibration anchor 覆盖，不修改 CV 或规则公式：

```bash
python src/rule_calibration_dataset.py
```

输出到 `data/output/rule_calibration_dataset/`：

- `01_face_profile_for_rules.csv`：每个编号一行，包含检测/pose 状态、五项连续特征及
  R01–R06 输入别名；失败行不补值。R07–R10 指标仅作 reference。
- `02_rule_feature_statistics.csv`：成功样本三项核心特征的 n、mean、median、样本
  standard deviation、min/max/range、P25/P75。分位数采用排序后 `(n-1)×p` 位置的
  线性插值。
- `03_current_calibration_coverage.csv`：读取当前 `RuleCalibration` 的 input/output
  anchors，分开记录端点附近计数与严格越界 clamp 计数。端点附近定义为在区间内、距
  low 或 high 不超过 input span 的 10%；等于端点不算越界。`output_semantics` 区分
  角度加法修正和参数乘数。
- `rule_calibration_dataset.json`：以上内容的严格 JSON，并记录统计方法与适用范围。
- `individual_profiles/`：逐张重新生成的 geometry、Face Profile、debug 图。

这些统计仅描述当前 Demo 样本分布，不代表人口分布、科学阈值或标准眼型边界。

## Reference Tutorial → Reference Action Geometry

教程侧和用户侧是两条独立数据链：

```text
Blogger local-eye tutorial → manual annotation → Reference Action Geometry
                                               → Standard Makeup Action
User full face → Face Profile v0.3 ────────────┘
                                               → Personalization Engine v0
                                               → Personalized Action
```

**Reference Action Geometry 描述教程动作，不是 Blogger Face Profile。** 局部眼图可以只有
单眼，也可以是上下 before/after 拼接图；不需要 face oval、双眼或完整眉毛。当前只标注
A04 Cat Eye Eyeliner 的 `eye_inner`、`eye_outer`、`eyeliner_tip` 三个必选点；
`eyeliner_start` 和 `upper_lash_outer_reference` 可选。拼接素材优先在 after 区域标注
自然眼轴和眼线终点；before 点不是必需输入。

### 数学定义与符号

使用截取后单眼图上的 pixel 点位，仅把 pixel 距离留作 debug：

```text
eye_axis = eye_outer - eye_inner
eyeliner_vector = eyeliner_tip - eye_outer
eye_width_px = ||eye_axis||
eyeliner_extension_ratio = ||eyeliner_vector|| / eye_width_px
screen_cross = eye_axis.x * eyeliner_vector.y - eye_axis.y * eyeliner_vector.x
dot = eye_axis · eyeliner_vector
direction_relative_to_eye_axis_deg =
    degrees(atan2(-sign(eye_axis.x) * screen_cross, dot))
start_position_ratio =
    dot(eyeliner_start - eye_inner, eye_axis) / dot(eye_axis, eye_axis)
```

图像 y 轴向下。对向屏幕左或右的自然眼轴，眼线相对眼轴向**视觉上方**抬升均为正角，
向下为负角。这个符号定义假设教程图大体正立；共同的小幅旋转不会改变相对角度。
`start_position_ratio` 是起点沿自然眼轴 inner→outer 的投影比例；垂直于眼轴的偏移不改变该值。
`eyeliner_start` 缺失时 `start_position_ratio` 为 JSON `null`，不会伪造数值。
局部图的分辨率不会直接进入最终产品参数。

### 人工标注与可视化

将素材放在 `examples/reference/cat_eye_reference.jpg` 后运行：

```bash
python src/reference_action_annotator.py --image examples/reference/cat_eye_reference.jpg
```

如果上半是 before、下半是 after，指定 after 裁剪；`--split` 是分界高度占原图高度的
比例，默认 0.5，但应按素材实际分界设置：

```bash
python src/reference_action_annotator.py \
  --image examples/reference/cat_eye_reference.jpg \
  --crop bottom --split 0.52
```

也可使用 `--roi X Y W H` 手工给原图框，或 `--select-roi` 在界面拖选。点击顺序为
`eye_inner`、`eye_outer`、`eyeliner_tip`，随后可选 `eyeliner_start`、
`upper_lash_outer_reference`。按 Enter 完成，`s` 跳过可选点，`u` 撤销上一点，Esc
取消。点击坐标属于**裁剪后的图像**；JSON 会记录原图 ROI，便于回溯。若已由人工确认
点位，可用 `--points-json points.json` 跳过 GUI，格式如下（仅示意，并非真实教程标注）：

```json
{
  "eye_inner": {"x": 20, "y": 80},
  "eye_outer": {"x": 120, "y": 80},
  "eyeliner_tip": {"x": 140, "y": 60},
  "eyeliner_start": {"x": 92, "y": 76}
}
```

输出 `data/output/reference_action/cat_eye_reference_annotation.json` 和
`cat_eye_reference_debug.jpg`。overlay 绘制标注点、自然眼轴、眼线向量及 extension
距离，并显示相对角度和 extension ratio，不绘制眼型标签。

ReferenceActionGeometry v0.1 的核心输出示例：

```json
{
  "version": "0.1",
  "reference_id": "cat_eye_main_demo",
  "action_id": "A04",
  "source_type": "local_eye_tutorial",
  "annotation": {
    "eye_inner": {"x": 0, "y": 0},
    "eye_outer": {"x": 100, "y": 0},
    "eyeliner_tip": {"x": 120, "y": -20}
  },
  "geometry": {
    "eye_width_px": 100.0,
    "eyeliner_extension_px": 28.284271,
    "eyeliner_extension_ratio": 0.282843,
    "direction_relative_to_eye_axis_deg": 45.0,
    "start_position_ratio": null
  },
  "quality": {
    "annotation_complete": true,
    "source_is_full_face": false,
    "manual_annotation": true
  }
}
```

### Standard Action adapter 与 fallback

`reference_action_adapter.py` 读取标注 JSON，将 A04 的参考角度与 extension ratio 写成
现有引擎可读的 baseline；A02 和其他手工 recipe 设置原样保留：

```bash
python src/reference_action_adapter.py \
  --reference data/output/reference_action/cat_eye_reference_annotation.json \
  --output-recipe data/output/reference_action/cat_eye_reference_recipe.json
```

新的 A04 同时保存语义明确的 `reference_parameters` 和 `source`：

```json
{
  "action_id": "A04",
  "parameters": {
    "direction_angle_deg": 45.0,
    "extension_factor": 1.0,
    "reference_extension_ratio": 0.282843,
    "target_region": "outer_third"
  },
  "reference_parameters": {
    "direction_relative_to_eye_axis_deg": 45.0,
    "reference_extension_ratio": 0.282843,
    "start_position_ratio": null
  },
  "source": {
    "type": "reference_tutorial_annotation",
    "reference_id": "cat_eye_main_demo"
  }
}
```

其中 `parameters.direction_angle_deg` 是现有 Personalization Engine 所需的字段别名，
对参考来源的 A04 表示**相对自然眼轴角度**。`reference_extension_ratio` 是参考眼线长度
除以参考眼宽的无量纲几何长度；`extension_factor=1.0` 是给现有 R03/R04 的中性乘数初值，
**不是**参考长度。adapter 对用户执行 R03/R04 后明确输出：

```text
extension_adaptation_factor = R03/R04 adjustment_value
personalized_extension_ratio = reference_extension_ratio * extension_adaptation_factor
```

三项均保存在 A04 的 `personalized_parameters` 中；原有 `extension_factor` 字段继续作为
乘数兼容现有规则引擎。没有参考几何时，旧人工 recipe 的 `extension_factor` 及其执行结果
保持不变。`start_position_ratio` 若有标注则进入 `parameters`
并被现有引擎原样保留；若没有，adapter 保留手工 recipe 中的
`target_region="outer_third"` 或已有的 `start_position_ratio`，不补造数值。
完整 provenance 保留在
生成的 Standard Recipe 中。

可直接接上用户正脸 profile，使用**未修改的** Personalization Engine：

```bash
python src/reference_action_adapter.py \
  --reference data/output/reference_action/cat_eye_reference_annotation.json \
  --user-profile data/output/rule_calibration_dataset/individual_profiles/face_01_face_profile.json
```

省略 `--reference` 时，adapter 深拷贝并使用原来的
`examples/cat_eye_standard_recipe.json` 人工 baseline，保持既有 fallback 行为。
当前 `examples/reference/cat_eye_reference.jpg` 的 finished-look 实际标注保存在
`data/output/reference_action/cat_eye_reference_annotation.json`；上面的 JSON 仍只是公式示例。

## Reference-Relative Personalization

Reference personalization 现在保留两种模式。`absolute` 仍是默认模式，返回值与既有
`personalize_reference_recipe` 完全一致：

```text
Absolute = Reference Action + User Profile correction
```

新增的 `reference_relative` 只升级 A04 direction 和 extension：

```text
direction_delta = correction(user eye tail) - correction(blogger eye tail)
personalized_direction = reference_direction + direction_delta

relative_extension_factor = factor(user relative eye length)
                            / factor(blogger relative eye length)
personalized_extension_ratio = reference_extension_ratio
                               * relative_extension_factor
```

两侧 correction/factor 都直接调用现有 R01–R04 mapping 和同一组 calibration anchors。
`start_position_ratio` 原样继承 Reference Action。A02 的 range/intensity 在 v0.1 中继续使用
现有 absolute personalization，因为当前 Reference Action Geometry 没有完整 A02 baseline。

Python API：

```python
from src.reference_relative_personalization import personalize_reference_with_mode

result = personalize_reference_with_mode(
    blogger_profile,
    stable_user_profile,
    reference_action_geometry,
    manual_recipe,
    mode="reference_relative",
)
```

省略 `mode` 时使用 `absolute`，保持向后兼容。也可以直接调用
`personalize_reference_relative(...)`。当 Blogger Face Profile 与 User Face Profile 完全
相同时，`identity_consistency` 保证 direction delta 严格为 `0`、extension factor 严格为
`1`，因此输出保持原教程 Reference Action 不变。

使用当前 Main Demo JSON 生成 absolute/relative 对照：

```bash
python -m src.reference_relative_personalization
```

输出写入 `data/output/reference_relative_personalization/`，包括两个 mode 的完整 JSON、
`absolute_vs_relative.csv`、连续数值解释 JSON 和 identity consistency 验证 JSON。

## Stable Face Scan v0.1

`Face Profile v0.3` 是**单帧测量**；`Stable Face Scan` 是多个单帧 Profile 的稳健聚合。
最终产品路径为多帧 → 每帧现有 Face Landmarker / roll normalization / Face Profile →
`FaceScanAggregator` → `aggregated_face_profile` → 未修改的 Personalization Engine。
聚合逻辑位于 `src/face_scan_aggregator.py`，不写入 `face_profile.py`。

相机侧可以逐帧调用 `aggregator.add_profile(profile, frame_id=...)`，采集结束后调用
`aggregator.finalize()`；检测失败可用 `add_failure(frame_id=..., reason=...)` 记录。
默认至少需要 **3 个有效 Profile**。有效性只检查 v0.3 完整字段、有限数值、非退化
几何以及 `pose_normalized=true`；失败帧保留原因但不补值。不会依据某项特征的偏离幅度
删除帧，也没有“好脸 / 坏脸”或美妆阈值。

核心 R01–R06 输入以及 R07–R10 的 reference/candidate 输入均逐帧计算 `n`、median、
mean、sample std、min/max/range、Q1/Q3/IQR、MAD。Q1/Q3 使用 inclusive linear
quartile；`MAD = median(|x - median(x)|)`。最终核心输入取各帧该字段的 **median**，
而不是单帧值或简单 mean。完整输出仍是 Face Profile v0.3 路径；每组 `mean` 保持
逐帧 mean 的 median，左右值用该组**有符号半差的 median** 重建，使聚合后左右平均
仍等于 `mean`。其他单值字段取 median。逐帧原始 Profile 不变。

图片入口复用现有 CV pipeline：

```bash
python -m src.face_scan_aggregator --images \
  data/input/stability_01.JPG data/input/stability_02.JPG \
  data/input/stability_03.JPG data/input/stability_04.JPG \
  data/input/stability_05.JPG
```

也可使用 `--profiles path/to/01.json path/to/02.json path/to/03.json`。若有同一份真实
Reference Action Geometry，可用 `--reference-geometry path/to/reference.json`；否则
使用当前人工 Cat Eye recipe。输出目录 `data/output/stable_face_scan_validation/` 包含
`stable_face_scan.json`、可直接传给现有规则引擎的 `stable_face_profile.json`、
`single_vs_stable_personalization.csv`、`stable_personalization.json`，图片入口另保存
每帧 Profile / geometry / debug 图。当前仅保留 R07–R10 作为测量参考，不执行规则。

## EyeLocalProfile v0.1

`EyeLocalProfile` 是单眼局部几何契约，与 Face Profile v0.3 平行。教程 bare eye 和用户
完整脸中的单眼都先适配成同一个 `EyeLocalKeypoints`，再进入同一套纯几何函数：

```text
tutorial visual points ─┐
                        ├→ EyeLocalKeypoints → EyeLocalProfile v0.1
MediaPipe 478 adapter ──┘
```

Schema 保持为：

```json
{
  "version": "0.1",
  "source_type": "tutorial_reference | user_face",
  "side": "left | right",
  "geometry": {
    "eye_width_px": 0.0,
    "eye_height_px": 0.0,
    "eye_width_height_ratio": 0.0,
    "eye_axis_angle_deg": 0.0,
    "inner_corner_angle_deg": 0.0,
    "lower_lid_space_ratio_local": null,
    "brow_eye_ratio_local": 0.0
  },
  "quality": {}
}
```

共同定义如下：

- `eye_width_px = distance(eye_inner, eye_outer)`；`eye_height_px =
  distance(eye_upper, eye_lower)`；宽高比为两者相除。
- `eye_axis_angle_deg` 是有方向的 inner→outer 向量相对图像水平轴的角度，图像 y 向下
  会先转换成数学坐标 y 向上。人物右眼在未镜像图中通常接近 180°。该字段只用于局部
  debug，不替代 Face Profile 的 `eye_tail_angle.mean`。
- `inner_corner_angle_deg` 以 `eye_inner` 为顶点、使用上下眼睑紧邻内眼角的两个点。
- `lower_lid_space_ratio_local` 是三个对应的下眼睑到眶下 mesh edge 距离均值除以单眼宽。
  教程人工图只有在同语义眶下参考链可可靠定位时才计算，否则为 JSON `null`。
- `brow_eye_ratio_local` 是五个 eye-facing brow contour 点的质心到自然眼轴的垂直距离，
  再除以单眼宽。教程 crop 未显示完整、可靠的眉毛时必须为 JSON `null`，不能用上眼睑
  或眼窝褶皱替代眉毛点。

face_05–11 当前选择人物右眼，对未镜像输入对应图片左侧；landmark 分别为 eye
`133/33/159/145`、inner neighbors `173/155`、lower/infra pairs
`144-24, 145-23, 153-22`、brow `46/53/52/65/55`。教程图只有一只眼，无法证明素材
是否镜像，因此 `side=right` 仅表示它与上述 inner-right/outer-left 方向匹配；质量字段
明确写入 `image_side=single_eye_crop`、`subject_side=unknown`、
`visual_estimation=true`、`human_confirmed=false`。

生成本轮验证数据：

```bash
python -m src.eye_local_profile_dataset
```

该命令输出每个样本的 EyeLocalProfile JSON、测量 debug 图、
`reference_vs_face05_11.csv`、`reference_and_users_full_report.csv` 和严格 JSON 汇总。
reference 行不伪造 full-face 值；无法可靠标注的教程 lower-lid 局部值保持为空。
当前教程 crop 的眉毛同样不可可靠定位，因此 `brow_eye_ratio_local` 也保持为空；
`inner_corner_angle_deg` 标记为 `validation_pending`，不进入生产规则。

## 测试

```bash
python -m unittest discover -s tests -v
```

## Main Demo Safe Fixtures

`data/fixtures/main_demo/` 提供 Product / My Tutorial 可直接读取的 Main Demo
结构化结果：Face06 是 multi-adaptation case，Face11 是 minimal-adaptation /
keep-reference case。两个 Face Profile fixture 都保留完整 v0.3 契约；personalization
fixture 同时保留 reference-relative 的 raw mapping、validation dead-zone 决策与最终
A04/A02 参数。

这些 fixture 只包含结构化 CV / personalization 结果，不包含用户原始图片、图片编码、
EXIF、debug image path 或本地绝对路径。拥有本地 validation outputs 时可重复生成：

```bash
python -m src.main_demo_safe_fixtures
```

## Tutorial Video → Reference Package

MIRA Main Demo v0.1 支持以下最小闭环：Tutorial Video → timestamp-based
BEFORE/A04/AFTER keyframe extraction → Blogger Face Profile v0.3 → 已有
Reference Action Geometry v0.1 → portable Reference Package → 已有 reference-relative
personalization + validation dead zone → A04/A02 AR Spatial Guidance。

视频桥接只保存视频 basename 和结构化结果；原视频、抽帧、CV debug 图继续放在被忽略的
`data/output/`。A04 annotation points 仍由人工标注 JSON 提供，不进行 eyeliner tip 自动
识别。当前 timestamps 可由 Tutorial Parser 或 Demo metadata 预先提供；本版本不声称已经
实现完整 automatic video understanding 或 photorealistic makeup try-on。

从视频生成 Reference Package：

```bash
python -m src.tutorial_video_reference \
  --video tutorial.mp4 \
  --before 3.2 --a04 108.5 --after 145.0 \
  --annotation examples/reference/a04_points.json \
  --output data/output/tutorial_video_reference/
```

Reference Package 与用户 Face Profile 可继续进入统一 Demo 命令。稳定演示使用
`existing_reference`；视频技术展示使用 `video_reference`：

```bash
python tools/run_main_demo_pipeline.py \
  --mode existing_reference --sample face_06 \
  --landmarks data/output/current_frame_eye_landmarks.json

python tools/run_main_demo_pipeline.py \
  --mode video_reference \
  --reference-package data/output/tutorial_video_reference/reference_package.json \
  --user-profile data/fixtures/main_demo/face_06_face_profile.json \
  --landmarks data/output/current_frame_eye_landmarks.json
```

AR 后端仅输出 normalized camera-space geometry。A04 是方向线；A02 是 lower-lid
target-region 窄带，intensity 仅作为 metadata，并不等同于 UI opacity。可选 debug
renderer 位于 `tools/render_ar_guidance_debug.py`，所有图片输出仍只写入
`data/output/`。

## Local Webcam Cat Eye Demo

本地 Webcam Demo 使用 Mac 默认摄像头完成一次 Stable Face Scan，然后基于
`cat_eye_main_demo` 生成一次个性化结果，并在后续帧中实时绘制 A04 眼线方向线
和 A02 下眼睑区域。建议使用仓库已有的 Python 3.9 `.venv`，其中已配置兼容的
MediaPipe 和 OpenCV：

```bash
cd beauty-face-engine
source .venv/bin/activate
python tools/run_cat_eye_webcam_demo.py
```

首次运行时，macOS 可能会请求 Terminal 或 Python 的 Camera 权限。默认扫描 30 个
有效帧，通常需要数秒，实际时间取决于光线、遮挡和设备性能；20 秒超时时，只要
已经收集至少 3 个有效帧就会继续。可通过 `--scan-target`、`--scan-timeout`、
`--camera` 和 `--side left|right` 调整；默认引导用户本人的右眼。

实时窗口快捷键：

- `P`：只显示 personalized guidance。
- `R`：只显示 Blogger Reference guidance。
- `B`：同时显示两者。
- `S`：仅保存结构化 JSON 到被 Git 忽略的 `data/output/webcam_cat_eye_demo/`。
- `Q`：退出。

摄像头原始帧在未镜像坐标中完成 landmark、Face Profile 和 AR 几何计算；仅在显示
阶段做水平镜像，因此 left/right 始终指用户本人的解剖学侧。程序不会自动保存
摄像头视频、帧图或 debug 图片。

每次启动并完成扫描后都会新建一个 session ID，绑定当次 Stable Face
Profile hash、personalization、Live Overlay 和保存结果。`data/output/` 只是
保存目标，程序不会从中读取旧 personalization 作为 Live State。当前版本
没有热键重新扫描；退出后再运行命令会建立一个全新 session，不保留上一轮
profile、personalization、AR snapshot 或 overlay summary 的对象引用。

## Special Area Preference v0.1

Special Area Preference 允许用户手动圈选自己在意、希望保留或希望处理的区域，
并自行选择 `KEEP`、`BLEND`、`COVER` 或 `HIGHLIGHT`。系统只保存用户选择的
normalized polygon、位置、可选标签和 preference，再据此生成 complexion/base
makeup 教程；不会自动检测或诊断区域类型，也不会自动推荐遮盖。

`user_label` 完全来自用户输入，`preference` 完全来自用户选择。教程输出中的
`decision_source` 固定为 `user_preference`。

内部左右语义始终采用用户本人视角：

- `subject_left_cheek`：被拍摄者／用户本人自己的左脸颊。
- `subject_right_cheek`：被拍摄者／用户本人自己的右脸颊。

`subject_left` 和 `subject_right` 永远不表示图片画面的左／右。对于正脸非镜像照片，
image-left 通常对应 subject-right，image-right 通常对应 subject-left，但当前版本不依赖
这一假设进行自动判断；location 仍由用户手动选择。不要使用 `image_left_cheek` 或
`image_right_cheek` 表示用户本人的左右脸颊。旧的歧义值 `left_cheek` 和
`right_cheek` 不属于 v0.1 合法枚举，也不会写入新输出。

本地图片 Demo：

```bash
python tools/run_special_area_image_demo.py \
  --image data/input/special_area_demo/subject01_front.jpg \
  --output data/output/special_area_demo/
```

左键添加 polygon 点；`Backspace` 或 `U` 撤销；`C` 清空；至少三个点后按
`Enter` 确认；`Q` 退出。输入图片、debug 图片和生成 JSON 都只保留在被 Git
忽略的 `data/input/`、`data/output/`，不会进入 fixture。

## Special Area Live Tracking v0.1

Live Tracking 将静态照片中由用户圈选的 normalized polygon 绑定到同一张脸的
MediaPipe landmarks。每个 polygon point 从附近 10 个 landmarks 中选择一个包含该点、
面积大于 epsilon 的非退化 triangle，并保存三个 landmark index 和 barycentric
weights。Webcam 每帧只需读取相同三个 landmarks，就可以重投影该 point。系统不检测
胎记、痣、疤痕或皮肤问题，也不会改变用户原先选择的 label、location 或 preference。

`SpecialAreaProfile v0.1` 继续表示“用户定义了什么”；独立的
`SpecialAreaTrackingBinding v0.1` 只表示“polygon 如何绑定到脸部 geometry”。Binding
保存 source profile SHA-256，Live Session 会拒绝来自其他或旧 Profile 的 binding。

所有 tracking geometry 均在 raw、unmirrored frame coordinates 中计算。只有最终显示
preview 和 polygon 时才水平镜像，因此 `subject_left`／`subject_right` 仍始终表示用户
本人左右侧，不会因镜像预览而交换。

使用已经输出新 `subject_*` location 的 Profile 运行：

```bash
python tools/run_special_area_webcam_demo.py \
  --image data/input/special_area_demo/subject01_front.jpg \
  --profile data/output/special_area_demo_blend/special_area_profile.json
```

Live UI：

- `Q`：退出。
- `S`：只保存当前 session JSON metadata；不保存 Webcam frame。
- `D`：显示／隐藏绑定 triangle 使用的 landmark anchors。
- `P`：显示／隐藏 preference guidance，不修改原始 preference。

检测不到脸或当前投影不安全时，UI 显示 `Tracking: FACE LOST`，并立即清除上一帧
polygon；重新检测到有效 landmarks 后恢复 `Tracking: ACTIVE`。v0.1 使用 raw
landmark reprojection，不做 temporal smoothing。

## Live Area Selection v0.1

Live Area Selection 把静态圈选步骤放进同一个本地 Camera session：

```text
Camera -> F Freeze -> Draw Polygon -> Confirm -> Label -> Location
       -> Preference -> Landmark Binding -> Live Tracking
```

启动时不需要 `--image` 或 `--profile`：

```bash
cd beauty-face-engine
.venv/bin/python tools/run_live_area_selection_demo.py
```

初始画面显示 `Tracking: NOT CONFIGURED`。按 `F` 后，当前 raw frame 和检测到的
478 landmarks 只保留在内存中；程序拒绝无脸或多脸冻结帧。圈选画面使用镜像 preview，
但点击会通过 `raw_x = 1 - display_x` 转回 raw、unmirrored normalized coordinates，
`y` 保持不变。因此 `subject_left_cheek` / `subject_right_cheek` 继续表示用户本人左右，
不表示屏幕左右。

确认 polygon 时，程序在 raw coordinates 中移除距离小于 `1e-4` 的重复点，再以点集
centroid 为中心按 `atan2` 极角重排现有点。它不会移动点、增加点或使用 convex hull。
重排后必须通过非相邻边相交检查和 shoelace 面积检查；自交、少于三个 unique points、
近共线或面积过小的 polygon 会被拒绝并要求重新圈选。Metadata 输入前会显示最终 normalized
polygon 和 `Polygon normalized: N points`。

圈选操作：左键添加点，`U` / `Backspace` 撤销，`C` 清空，`Enter` / `Space`
确认，`Esc` 取消，`Q` 退出。确认后必须显式选择 location 和
`KEEP` / `BLEND` / `COVER` / `HIGHLIGHT`；系统不推断区域类型、location 或
preference。Profile 和 TrackingBinding 直接由内存中的 freeze landmarks 与 raw polygon
构建，并在开始 tracking 前通过 identity reprojection 检查。

进入 Live 后：`F` 重新圈选，`S` 只保存 Profile、Binding 和 session JSON metadata，
`D` 切换 triangle anchors，`P` 切换 guidance，`Q` 退出。重新圈选在新 binding 完整验证
通过后才替换旧 selection；按 `Esc` 会恢复旧 selection。v0.1 每个 session 只支持一个
active area，不保存 freeze frame、Webcam frame、截图或视频。

该流程不做自动检测、诊断或 face identity verification。它假设圈选后继续出现在同一
Camera session 中的人仍是当前用户；如果换人，landmark geometry 仍可能继续投影。

## 模块设计

- `FaceLandmarkerDetector`：负责配置和调用 MediaPipe Tasks Face Landmarker。
- `eye_landmarks.py`：复制 8 个眼部点和两个五点眉毛轮廓，不修改原始 MediaPipe 结果。
- `face_geometry.py`：只接收二维点，使用 Euclidean distance，不依赖 MediaPipe/OpenCV。
- `makeup_rules.py`：保存显式、可测试的 R01–R06 连续映射和 R07–R10 状态。
- `personalization_engine.py`：只消费 Face Profile v0.3 和 Standard Makeup Action，保留
  `original_parameters` 并输出有限 JSON 数值。

当前版本不包含眼型/眼距/眼尾分类、Face Profile 标签、美妆分类 threshold、AR，
也不使用 LLM 决定个性化数值。Personalization Engine v0 仅支持 `cat_eye` 下的 A04/A02
和 R01–R06。

## Week 1 后端更新

- 后端以 FastAPI + SQLite 提供教程解析、Recipe 查询、Beauty Kit、Matching、CV Adaptation 与 Explanation 的稳定接口。
- 教程解析器当前使用离线 `MockTutorialVisionProvider`，将视频/帧目录引用转换为经校验的五步骤 `StandardRecipe`；真实视频理解 Provider 尚未接入。
- CV 的 `Face Profile v0.1` 仍由 `src/face_profile.py` 维护；后端只校验并原样消费，不增加脸型或美学判断。
- Matching 已使用结构化 Product Capability 做确定性评分：Color 30%、Finish 25%、Depth 15%、Pigmentation 10%、Texture 10%、Functional 10%。品类及 Matte/Shimmer/Glitter 冲突先经过硬约束；未验证属性不生成分数。当前只有演示大地色眼影盘具备完整的已验证 fixture，目录中的品牌候选产品仍标记为能力数据未验证。CV Adaptation 与 Explanation 仍是结构性占位。
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
Personalization Engine v0 (R01–R06)
```

`Face Profile` 是几何层与个性化阶段之间的稳定数据契约，只重新组织已计算的连续参数。
Personalization Engine 消费该契约，不重复几何计算，也不生成眼型、眼距或美学分类。

## R01–R10 Rule Mapping

- R01/R02：`eye_tail_angle` → eyeliner direction
- R03/R04：`relative_eye_length` → eyeliner extension
- R05/R06：`lower_lid_space_ratio` → lower lashline range
- R07/R08：`inner_corner_angle` → inner-corner makeup action（`validation_only`）
- R09/R10：`brow_eye_ratio` → upper blending height（`candidate`）

以上 mapping 只声明规则所消费的连续输入，不在 Vision Engine 中定义分类阈值或生成
美学结论。

## Current Limitations

- 当前只进行二维 roll normalization，尚未补偿 yaw/pitch 三维透视。
- Eye tail angle 仍可能受到 yaw、pitch、眼睑开合和眼角 landmark 抖动影响。
- Eye height 可能受到眨眼和其他面部表情影响。
- Brow landmarks 可能受到头发、妆容或其他遮挡影响。
- Relative eye length 仍会受到 yaw、透视和侧向 face-oval landmark 位置影响。
- Lower lid space ratio 会受到 pitch、眯眼、笑容和下眼睑表情影响。
- Inner corner angle 会受到眼睑开合、内眼角遮挡、分辨率和 head pose 影响。

## Output Files

- `landmarks_result.jpg`：全部 478 个 face landmarks 的检测验证图。
- `eye_landmarks_result.jpg`：眼部关键点、眼轴和眉眼测量 debug 图。
- `face_geometry.json`：包含 landmarks 坐标与测量过程的底层几何数据。
- `face_profile.json`：供后续 Personalization Engine 使用的连续参数契约。
- `repeatability_report.json`：保留的 Face Profile v0.2 重复性 baseline。
- `repeatability_report_v0.3.json`：v0.3 统计、逐图原始值及 v0.2 对比。
- `repeatability_report_v0.3.csv`：每个核心指标一行，附带全部输入照片的原始值列。
- `repeatability_v0.3/`：每张样本的 geometry、Face Profile v0.3 和 debug 图。
- `personalization_demo/personalization_demo.json`：三位真人 profile 使用同一 recipe 的完整结果。
- `personalization_demo/personalization_comparison.csv`：三人核心输入、输出参数和 applied rules 对比。
- `new_input_validation/`：新真人输入的逐人 profile、个性化输出和横向比较报告。
- `reference_action/`：局部教程标注 JSON、debug overlay、适配后的 Standard Recipe
  和可选的 Personalized Action。
- `eye_local_profile/`：教程 bare eye 与 face_05–11 的单眼 Profile、debug 图、局部对比表、
  full-face + local 联合表和严格 JSON 汇总。
