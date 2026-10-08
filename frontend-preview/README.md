# MIRA 映己 · 前端 Demo

中文美妆教程演示，使用 React、Vite 和 TypeScript。前端可连接现有 FastAPI，也可独立使用离线演示数据。

## 本地启动

```sh
npm ci
npm run dev
```

打开 http://127.0.0.1:5173 。生产检查使用 `npm run build`。静态托管需要配置 SPA fallback 到 `index.html`，保证子路由可以直接打开。

不启动后端时，`.env.example` 的默认配置会使用完整离线演示数据。

## 接入现有 FastAPI

前端包含 DTO、adapter、统一 API client、错误处理和 Mock fallback。页面只调用 `src/services/`，不直接请求后端。`backend-reference/` 是只读后端参考，不需要修改其业务代码或说明文档。

### 1. 准备并启动后端

在项目根目录准备 Python 环境：

```sh
python3 -m venv .runtime/api-venv
.runtime/api-venv/bin/pip install -r backend-reference/requirements.txt
```

数据库使用项目下的 `.runtime/mira_week1.db`。将下面的数据库路径替换为当前项目的绝对路径，然后启动 FastAPI：

```sh
cd backend-reference
MIRA_DATABASE_URL=sqlite:////absolute/path/to/mira-demo/.runtime/mira_week1.db \
  ../.runtime/api-venv/bin/uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

健康检查地址为 http://127.0.0.1:8000/health 。

### 2. 配置并启动前端

```sh
cp .env.example .env.local
```

真实 API + Mock fallback 推荐配置：

```env
VITE_DEMO_MODE=false
VITE_MOCK_FALLBACK=true
VITE_API_BASE_URL=/api
VITE_API_TIMEOUT_MS=30000
VITE_EXAMPLE_MEDIA_PATH=data/input/main_eye_tutorial.mp4
VITE_EXAMPLE_MEDIA_KIND=video
```

```sh
npm ci
npm run dev -- --port 5173
```

开发环境中，Vite 将 `/api/*` 代理到 `http://127.0.0.1:8000/*`。生产环境需要提供同源 `/api` 反向代理，或将 `VITE_API_BASE_URL` 指向已配置 CORS 的后端地址。

### 3. 数据来源

- 真实接口：`POST /tutorials/parse`、`GET /recipes/:id`、`GET /beauty-kit`、`POST /matching`，以及有真实 Face Profile 时的 `POST /cv-adaptation`。
- 前端补充：产品品牌、图片、色号和质地等后端暂缺的展示资料。
- 演示数据：Parsing 阶段与关键画面、扫描质量、色彩分析、个性化动作和实时指导。
- `VITE_MOCK_FALLBACK=true` 时，真实请求失败会回退到演示数据并保留来源提示；设为 `false` 可进行严格联调。

## 体验流程

首页 → 添加参考教程 → 解析 → 配方 → 美妆工具库 → 产品匹配 → 扫描说明。

- 同意扫描：示例取景状态 → 示例面部档案 → 专属教程 → 实时指导 → 完成。
- 暂不扫描：直接生成仅结合教程和产品的教程。
- 上传与链接目前只记录输入，不上传文件；示例教程可通过配置的后端可读媒体路径调用真实解析接口。
- 添加产品入口保留为演示流程，识别、搜索和手动保存尚未接入。
- 语音按钮展示可点击意图，不启用麦克风。
- 保存的教程位于浏览器 localStorage；流程状态和面部选择位于 sessionStorage。当前没有账户、云存储或真实面部采集。

## 前端结构

- `src/types/`：页面使用的 domain types。
- `src/services/api/`：统一 API client 和后端 DTO。
- `src/services/adapters/`：后端 contract 到现有 domain model 的映射。
- `src/services/`：页面数据边界，负责 API 请求、适配和 fallback。
- `src/mocks/`：离线演示及接口 fallback 数据。
- `src/pages/`：页面，只通过 services 获取数据。
- `src/components/`：布局、基础 UI、教程、产品和扫描组件。
- `src/lib/config.ts`：API 地址、超时、Demo 模式和 fallback 配置。

面部摄像头组件与 AR overlay 已分离；AR 坐标为 0–100 的归一化示意坐标。Parsing 的阶段动画是前端视觉进度，不代表后端任务进度。

更详细的字段映射与数据来源说明见 [ADAPTATION.md](./ADAPTATION.md)，真实联调记录见 [INTEGRATION.md](./INTEGRATION.md)。

## 素材

品牌素材位于 `public/assets/brand/`，教程素材位于 `public/assets/tutorial/`，扫描说明图片位于 `public/assets/face/`。产品图片通过本地 metadata 补充，拆解关键帧仍保留占位。

## 验证

```sh
npm test
npm run build
```

实时后端可用时可运行：

```sh
npm run test:live
```
