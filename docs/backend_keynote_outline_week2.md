# MIRA Week 2｜后端技术说明 Keynote 大纲

> 用途：约 5 页、面向产品与工程团队的技术说明。重点讲清后端如何把教程动作、用户产品、CV 个性化结果组织成可供前端展示的教程；不把尚未完成的真实产品数据或映射说成已就绪。

## 第 1 页｜后端负责把模块接成一条可追踪的链路

**标题**

从教程动作到个性化步骤：MIRA Week 2 后端

**页面要点**

- FastAPI 提供解析、产品、匹配、CV 适配与 My Tutorial 等 API。
- 后端用共享 DTO 把 Parser、Product Matching、CV 与前端连接起来。
- SQLite 保存配方、Beauty Kit、产品能力与匹配/运行记录；请求通过 `request_id` 串联排查。
- 后端编排并校验数据，不接管 CV 的几何或个性化算法。

**主视觉建议**

用一条水平流程做主视觉：

`教程输入 → StandardRecipe → 产品匹配 → CV 个性化 → 模板解释 → MyTutorialResponse → 前端`

API 边界放在流程左侧，SQLite 与 request trace 放在流程下方，连接到需要持久化或追踪的服务。

**讲述提示**

“后端的核心价值不是再造一个算法，而是让各模块通过稳定契约协作，并且每一步都能追溯来源。”

## 第 2 页｜共享契约定义模块之间交换什么

**标题**

先统一数据，再连接服务

**页面要点**

- **StandardRecipe v1**：每个动作包含 `step_index`、`area`、`goal`、`product_requirement`、`tool`、`motion`、`intensity`、`target_result`。
- **BeautyKit / ProductCapability**：描述用户拥有什么产品，以及产品支持的区域、目标、要求和适用属性。
- **Face Profile v0.3**：CV 所有；后端验证版本与结构，保留原始 CV 字段，不复制一套几何模型。
- **MatchResult / MyTutorialResponse v0.2**：向下游提供匹配证据，最终向前端提供教程步骤与状态。

**接口概览（可做成分组卡片）**

- 入口：`POST /tutorials/parse`
- 产品：`GET/POST/PUT/DELETE /beauty-kit`、`GET /product-capabilities`
- 匹配：`POST /matching`
- 教程编排：`POST /tutorials/my-tutorial`
- 辅助：`GET /health`、`GET /recipes/{recipe_id}`、`POST /cv-adaptation`

**讲述提示**

“契约明确每个模块的输入、输出和版本。这样前端消费的是稳定 DTO，CV 仍然拥有自己的 Profile 和数值语义。”

## 第 3 页｜Product Matching 是确定性、可解释的决策

**标题**

先检查能不能用，再判断匹配得好不好

**页面要点**

1. 从 StandardRecipe 读取动作的产品要求。
2. 对照用户 Beauty Kit 与 ProductCapability。
3. 先执行硬约束检查；缺能力或存在功能冲突时明确标出，不让相似色号掩盖不可用条件。
4. 对通过条件检查的候选做确定性评分，并返回理由、差异、影响、满足/缺失能力及评分证据。

**主视觉建议**

画成“输入 → 硬约束闸门 → 确定性评分 → MatchResult”的决策图。闸门旁标出四类演示结果：强匹配、低匹配、缺少能力、功能冲突。

**讲述提示**

“分数不是 LLM 生成的；每个结果都能回看动作要求、候选产品能力、约束失败原因和评分组成。”

**演示数据说明**

当前用于集成演示的部分产品与能力 fixture 明确标为 synthetic/demo，并非真实产品 Ground Truth。真实品牌、色号和功能能力数据仍需产品侧补齐。

## 第 4 页｜CV 边界：后端负责适配，不改写个性化结果

**标题**

CV 决定数值，后端保留来源并组织调用

**页面要点**

- Face Profile v0.3 由后端校验，CV 几何字段仍由 CV 定义与维护。
- `decoded-action adapter` 通过显式映射配置，将可支持的配方动作映射到 CV action，并记录源 `step_index` 与 mapping version。
- 映射获准后调用现有 CV personalization；CV 返回的参数、调整值与 rule IDs 原样保留。
- 输出附带 recipe/action、Profile 版本、映射版本、规则及 request ID 等 provenance。

**主视觉建议**

把边界画清楚：`StandardRecipe → Backend Adapter → CV Engine → PersonalizedAction`。在 CV Engine 周围加边界框，标注“CV-owned：算法与数值”；在 Adapter 旁标注“backend-owned：显式映射与来源追踪”。

**讲述提示**

“适配器只做有依据的转换。没有批准的映射或必需输入时，步骤会降级为 unsupported/fallback，不会猜测 CV 数值。”

**当前限制**

生产映射配置仍需要获批的动作映射和基准输入；目前可用的 synthetic demo mapping 不能当作真实产品或生产 Ground Truth。

## 第 5 页｜Orchestrator 组装前端可渲染的教程

**标题**

一条请求，得到完整且可解释的 My Tutorial

**页面要点**

- `MyTutorialOrchestrator` 按 recipe action 依次运行匹配、CV action 映射、个性化与模板解释。
- 不支持 CV 个性化的动作仍保留为教程步骤，不会导致整份教程失败。
- 缺少能力、低匹配或功能冲突会显式出现在结果中；不静默替换产品。
- `MyTutorialResponse v0.2` 提供 `where / how / why / stop_when`、参数、匹配证据、个性化状态、provenance 与 fallback 状态。
- 前端负责呈现；后端负责业务编排和确定性模板，不在本流程中接入外部 LLM 或 AR。

**主视觉建议**

左侧放一个精简 response 卡片（动作、Where/How/Why/Stop When、状态），右侧用细线连接其来源：recipe step、MatchResult、Face Profile/CV action、解释模板。底部用 `request_id` 贯穿全链路。

**讲述提示 / 收尾**

“当前骨架可以端到端生成可渲染、可追溯的教程结构。下一步重点是补齐真实产品 Ground Truth 和经过确认的生产 action mapping，而不是改变 CV 算法。”

## 当前实现边界（制作时请保留）

- Parser 的本地默认解析 provider 是 mock/offline provider；不要描述为已接入生产级视频理解服务。
- 产品匹配算法已实现，但部分集成 fixture 是 synthetic/demo，不等于已拥有真实 30 色产品数据。
- Face Profile v0.3 校验与 CV action adapter 已有；adapter 不代表所有动作都具备获批的生产映射。
- `/cv-adaptation` 是兼容/校验边界，不要把它说成完整的 Face Scan API。
- My Tutorial 的模板解释是确定性的；不要声称已经调用外部 LLM。
- 当前范围不包含 AR 坐标/多边形生产契约。

## 仓库依据

- API 路由与 request ID：`src/api/app.py`
- 配方与 Beauty Kit 契约：`src/contracts/makeup.py`、`src/contracts/beauty_kit.py`
- Face Profile / CV 契约：`src/contracts/cv_adaptation.py`、`src/contracts/cv_actions.py`
- 产品匹配：`src/services/product_matching.py`
- 解码动作适配：`src/services/decoded_action_adapter.py`、`data/fixtures/decoded_cv_action_mapping_v1.json`
- My Tutorial 编排与响应：`src/services/my_tutorial_orchestrator.py`、`src/contracts/my_tutorial.py`
- 模板解释：`src/services/tutorial_explanation.py`
- SQLite ORM：`src/db/models.py`
- 演示数据标记：`data/fixtures/product_capabilities_orchestration_demo_v1.json`

---

## 交接给新 Codex 会话的制作 Prompt

```text
请基于仓库文件 docs/backend_keynote_outline_week2.md，制作一份约 5 页的中文 Keynote 技术说明演示稿，主题是 MIRA Week 2 后端基本架构。

受众：产品、前端、CV 与后端团队。目标是让听众快速理解后端模块边界、数据契约、确定性产品匹配、CV 数值权威边界，以及 My Tutorial 的端到端编排。

制作要求：
- 控制在 5 页左右，按 Markdown 中的五页结构组织；每页聚焦一个结论，避免堆字。
- 保留“当前实现边界”中的事实限定，不把 mock provider、synthetic demo product/mapping、尚未接通的生产能力说成已完成。
- 不改 CV 算法或数值、不虚构产品 Ground Truth、不加入未实现的 AR、外部 LLM 或生产视频理解能力。
- 使用清晰、现代、克制的技术产品风格；用可编辑的流程图/边界图表达架构，避免装饰性图表和虚构界面截图。
- 主流程至少体现：StandardRecipe → Product Matching → CV action adapter / personalization → Template Explanation → MyTutorialResponse v0.2 → Frontend；另外表达 Face Profile v0.3 与 request_id/provenance 的位置。
- 将讲述提示整理为每页 presenter notes（如果制作工具支持）；如不支持，放在单独的讲者备注页或交付说明中。
- 如需核实实现细节，以仓库当前代码为准；若与大纲不一致，先标出差异，不要自行扩大能力声明。
- 输出可继续编辑的 Keynote 文件；若当前环境无法生成原生 .key，则交付可编辑 PPTX，并说明格式限制。把成品保存到仓库的 docs/ 目录，不要提交或推送。

完成后报告成品路径、页数、采用的架构图和任何无法满足的 Keynote 原生格式限制。
```
