# 最新本地后端兼容入口

此目录仅提供 HTTP transport。默认通过 PYTHONPATH 调用当前仓库根目录的模块，不修改后端算法。face_scan_transport.py 保留此前已验证的上传包装器。

安装（项目根目录）：

```sh
python3 -m venv .runtime/latest-backend-venv
.runtime/latest-backend-venv/bin/pip install -r ../requirements.txt -r integration/requirements.txt -c integration/constraints.txt
sh integration/start.sh
```

数据库仍为 `.runtime/mira_week1.db`。默认地址 127.0.0.1:8000；前端 `/api` 代理保持不变。

保留原版的7个接口，并增加 `/face-scan`、`/personalization` 兼容路由与 `/special-area-guidance`。
新增接口输入为 `{profile: SpecialAreaProfile v0.1}`，输出直接来自 `adapt_special_area_tutorial`。不保存照片、区域或请求正文。

当前前端 keep/soften/cover 映射 KEEP/BLEND/COVER，椭圆选区转换为归一化多边形。位置为 other，不根据图上点击推断左右脸。用户未填写标签，因此 user_label 为空。
现有 integrate 的两个子选项与后端 HIGHLIGHT 不完全同义，继续前端指导；缺少选区的历史记录同样保留。所有结果包含 source，原有 stopWhen 与步骤关联保留前端来源。

未开放实时摄像头追踪、视频抽帧和 AR HTTP 端点：这些模块需要本轮流程尚未采集的关键点流、参考人物档案、手动标注和时间点。

新下载目录的 models 文件夹为空。启动脚本默认复用前端已有的 `public/models/face/face_landmarker.task`，可通过 MIRA_FACE_MODEL_PATH 覆盖；无需再次下载或修改桌面后端目录。

## 上传与解析

`POST /media/preview` 接收 multipart 文件并返回 upload_id、preview_path；文件保存在系统临时目录，1 小时后不可用，下次请求时清理。
`POST /tutorials/parse-upload` 接收 `{upload_id, title}`，仅从上传目录取文件，图片作为单帧目录、视频作为文件传给 app.state.tutorial_parser.provider。结果经 StandardRecipe 校验和保存，允许实际步骤数。
当前仍未配置真实 vision provider，该入口返回 503 vision_not_configured，不会调用 MockTutorialVisionProvider 或伪造上传解析结果。需要根据用户选定的模型服务实现 provider；测试使用替身验证传递与保存，不代表真实模型识别成功。
