# Week 1 多模态与后端说明

本文件由 Multimodal AI + Backend 维护，与 CV 的根目录 `README.md` 分离。

## 契约与教程解析

CV 的 `Face Profile v0.1` 契约由 `src/face_profile.py` 维护。后端仅通过
CV Adaptation envelope 原样校验和消费该 JSON，不加入脸型标签、阈值或美学判断。

`src/contracts/` 提供带版本的 Pydantic v2 契约：`StandardRecipe`、Beauty Kit、
Product Capability、MatchingResult，以及 CV/LLM 交接 envelope。

Week 1 教程解析流程为：

```text
教程视频或按顺序提取的帧目录
  → Provider adapter 接收多模态提示词
  → 五个经校验的 MakeupActionUnit
  → StandardRecipe
```

`MockTutorialVisionProvider` 支持离线测试和本地契约演示，但不能替代真实的视频理解。
后续真实 Provider 应实现 `TutorialVisionProvider.extract_action_units()`，并返回
`{"action_units": [...]}`。提示词位于 `src/services/tutorial_prompt.py`，与应用逻辑分离。

当前没有提交教程视频资源；主演示使用约定占位路径
`data/input/main_eye_tutorial.mp4`。个人或受版权保护的视频会被 Git 忽略；合成 fixtures
位于 `data/fixtures/`。

## 本地 API 与 SQLite

请在 Python 3.9–3.12 虚拟环境中安装依赖：

```bash
python -m pip install -r requirements.txt
uvicorn src.api.app:app --reload
```

本地 SQLite 默认数据库为 `data/mira_week1.db`（Git 忽略）。应用通过 `create_all`
初始化表，并自动写入 Beauty Kit/Product Capability fixtures。可使用
`MIRA_DATABASE_URL` 覆盖数据库地址。

Mock 模式不需要 API key、OpenCV 或 MediaPipe；教程路径仅作为 PoC 元数据。

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/tutorials/parse \
  -H 'content-type: application/json' \
  -d '{"media_path":"data/input/main_eye_tutorial.mp4","media_kind":"video","recipe_id":"recipe-main-eye-demo-v1","title":"Main eye tutorial demo"}'

curl http://127.0.0.1:8000/recipes/recipe-main-eye-demo-v1
curl http://127.0.0.1:8000/beauty-kit
```

已实现：健康检查、mock 教程解析、五步骤 Recipe 校验、Recipe 持久化/查询、示例 Beauty Kit
查询，以及 Face Profile 兼容性校验。

`POST /matching` 使用 Recipe 中的结构化需求与 Beauty Kit 的已验证 Product Capability
执行确定性评分，并返回理由、差异、妆效影响、缺失能力和硬约束。未验证产品不生成百分比。
`POST /cv-adaptation` 不执行个性化；`POST /explanations` 不调用 LLM。

## 调试与可观测性

API 向 `mira` 应用日志输出结构化 JSON。每个响应有 `X-Request-ID` header；错误响应体也有
`request_id`。用该 ID 可串联解析、持久化、匹配、CV 校验与解释生成的日志。

仅供开发环境使用的 Parser run 持久化：

```bash
MIRA_DEBUG_RUNS=1 uvicorn src.api.app:app --reload
```

这会把 Provider、可选 model name、提示词/Schema 版本、媒体*引用*、原始 Provider 输出、
校验结果/错误与耗时写入本地 SQLite 的 `parser_runs`。不会保存视频/帧字节、上传媒体、API key
或 secret。原始输出仍可能含用户来源文字，因此只应在本地开发开启。

无需调用模型即可重新校验已保存 run：

```bash
python -m src.tools.replay_parser_run <run_id>
```

对非默认数据库使用 `--database-url`。Replay 只读取保存的原始模型输出，再执行当前
Pydantic Recipe 校验。

## 当前限制

- 教程解析器当前使用 `MockTutorialVisionProvider`；尚未接入真实视频/帧理解模型，也未提交主演示视频。
- Week 1 教程解析路径固定要求五个步骤；`StandardRecipe` 契约本身允许任意非空的有序步骤。
- Matching 当前只有演示大地色眼影盘具备完整的已验证能力 fixture；目录中的其他展示产品仍为 `capability-unverified`，不会按品牌或名称推断能力。当前评分用于 Demo 决策解释，不代表官方产品 Ground Truth。
- CV Adaptation 只校验并透传 CV 的 `Face Profile v0.1`，不调用 CV 推理，也不做个性化调整。
- Explanation 为固定占位文案，未接入外部 LLM。
- SQLite 与 `create_all` 仅适合本地 Week 1 演示；没有迁移、鉴权、多用户隔离或生产级并发保障。
- `MIRA_DEBUG_RUNS=1` 会持久化原始 Provider 输出；不要提交调试数据库或可能含用户来源文字的诊断记录。
