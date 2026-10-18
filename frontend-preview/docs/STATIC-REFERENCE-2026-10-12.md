# 静态照片与局部偏好适配

## 本轮实现

- 保留 integrate/natural 与 integrate/highlight，不强行映射到后端 HIGHLIGHT；指导卡显示「前端呈现建议」或「局部底妆规则建议」。
- 选区新增 imageSource/imageId。示意图与旧照片上的区域不能作为当前照片的定位；保留偏好，但编辑需要重新选区。本人照片按原比例展示，避免裁切导致选区偏移。
- 扫描成功后，在内存保留同一张回看照片及其关键点；不写入 localStorage/sessionStorage。撤销同意、重扫清除；刷新丢失。用途说明包含静态上妆指导。
- 新增 GET /references/cat-eye：人工整理的 A02 下眼睑、A04 眼尾方向两步参考，几何来源为最新后端已有 main_demo_reference.json，并非用户上传的紫色教程测量结果。
- 新增 POST /guidance/static：接收照片标识、关键点、v0.3 档案、参考标识与 action_id；复用 package_existing_reference、personalize_reference_package、build_a02_guidance、build_a04_guidance。返回照片对应的双眼区域/线条，不保存输入，也不上传照片像素。
- 选择「试试示例教程」时直接展开参考内容，不另设入口或显示人工整理标签；不替换当前教程步骤或原 personalization 结果。只有本次照片可用时才能请求定位，失败保留错误而不绘制假位置。

## 验证与边界

- 前端 42 个测试通过，7 个原有 live 测试在普通测试命令中跳过；构建通过。
- 新后端测试覆盖双眼 A02/A04、参考读取、不支持参考及缺失关键点。
- 实际 HTTP 使用项目扫描示意图完成 Face Landmarker → /face-scan → /guidance/static，A02/A04 均为 200；不代表真人定位精度测试。
- 浏览器安全校验不可用，未完成桌面/移动端目视检查。
- 不启用实时追踪、动态摄像头 AR、视频自动抽帧/识别。没有将示意图区域变成真实追踪绑定。
- 没有配置识别模型 API，没有改动桌面后端算法。
