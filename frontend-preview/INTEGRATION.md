# 本地真实后端联调

当前 `.env.local` 已设置真实 API 模式并保留 Mock fallback：`VITE_DEMO_MODE=false`、`VITE_MOCK_FALLBACK=true`。前端通过 `/api` 代理到现有 FastAPI，没有修改 backend-reference 的业务代码。参考目录没有写入数据库或 Python 缓存。

预览： http://127.0.0.1:5173/tutorial
后端： http://127.0.0.1:8000
API 文档： http://127.0.0.1:8000/docs

## 启动

前端在 mira-demo 下运行：

```sh
npm run dev -- --port 5173 --strictPort
```

后端依赖安装在 `.runtime/api-venv`；FastAPI 的纯 HTTP 模式无需 MediaPipe。数据库为 `.runtime/mira_week1.db`。重启后端时，在 mira-demo 下运行：

```sh
MIRA_DATABASE_URL="sqlite:///$PWD/.runtime/mira_week1.db" PYTHONDONTWRITEBYTECODE=1 .runtime/api-venv/bin/python -B -m uvicorn src.api.app:app --app-dir backend-reference --host 127.0.0.1 --port 8000
```

## 实测结果

浏览器实际点击：Tutorial Input（使用示例）→ Parsing → Recipe → Beauty Kit → Matching。后端日志确认 POST /tutorials/parse 200；SQLite 保存配方；页面正确显示 5 步及 0–55 秒分段。GET /beauty-kit 200，显示后端 Neutral palette。POST /matching 200，5 个 unmatched 转为 missing、分数显示“未提供”。刷新 Matching 后通过 GET /recipes/:id 恢复同一配方，步骤对应正确。跳过扫描后 My Tutorial 展示标准动作 fallback。

真实 HTTP 测试额外验证 GET /recipes/:id 内容、完整 matching DTO 请求、POST /cv-adaptation 的 v0.1 合成样例校验/透传、失效配方恢复、错误端点下的 Mock fallback。

发现并修复：缓存的 Recipe ID 在数据库重置后返回 404，原实现直接报错/降级。现实现只在 404 时清除旧 ID，并根据现有媒体输入重新解析；其他错误保留原错误处理与 fallback。Recipe 页补充 fallback 提示。Matching 页明确说明后端占位，避免把 0/5 视为真实能力结论。

## 真实接口与演示边界

HTTP、SQLite、解析响应、配方读取、Beauty Kit、Matching 及 CV 校验均为真实后端调用。后端仍使用 MockTutorialVisionProvider，示例视频路径按后端文档作为元数据，不存在真实视频理解；上传文件和远程链接仍走前端 fallback。Matching 算法尚未实现，所以全 unmatched 是后端原有占位结果。

POST /cv-adaptation 已使用仓库合成 fixture 联调，不代表真实摄像头测量。当前没有 Face Scan HTTP 入口、模型文件或自拍素材，扫描质量、面部档案颜色字段、个性化动作和 AR/coach 继续 mock/标准动作 fallback。未把合成 fixture 注入为用户真实面部扫描。

## 验证

- npm test：10 个单元/服务回归测试通过，3 个 live 测试默认跳过。
- npm run test:live：3 个真实 HTTP 测试通过（需要两端运行）。
- 后端既有 test_api.py：9 个测试通过；以 in-memory 数据库、禁用字节码写入执行，避免修改参考目录。
- npm run build：成功；主 JS 约 505 kB，仍有非阻塞体积警告。

本轮修改：`.env.local`、`.gitignore`、`src/services/tutorial.ts`、`src/pages/Recipe.tsx`、`src/pages/Matching.tsx`、`tests/live-api.test.mjs`、`package.json`、`ADAPTATION.md`、`INTEGRATION.md`。新增本地运行环境 `.runtime/`，构建产物已更新。没有视觉重构。
