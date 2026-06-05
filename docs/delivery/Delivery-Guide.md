# TechBrief MVP 交付说明（Web / Admin / Workflow）

更新时间：2026-06-04

## 1. 交付范围（MVP）

- 来源：OpenAI、Anthropic
- 内容类型：公开文章、来自更多公开视频平台的公开视频资料
- 端到端流水线：`discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending -> publish -> notify`
- 产品形态：公开 Web 站点 + 后台管理系统 + 定时工作流
- 存储：PostgreSQL 作为主业务库，腾讯云 COS 作为原始大对象存储
- 邮件能力：直接订阅成功、退订、每日汇总邮件、投递回执与重发
- 微信公众号能力：后台中的手动草稿创建工具，不属于自动主流程

## 2. 目标交付物

### 2.1 文档

- [TechBrief-PRD.md](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md)
- [Technical-Solution-Report.md](file:///home/shixuan/code/TechBrief/docs/delivery/Technical-Solution-Report.md)
- [Database-Design.md](file:///home/shixuan/code/TechBrief/docs/delivery/Database-Design.md)
- [API-Design.md](file:///home/shixuan/code/TechBrief/docs/delivery/API-Design.md)
- [System-Architecture.md](file:///home/shixuan/code/TechBrief/docs/delivery/System-Architecture.md)
- [Acceptance-Checklist.md](file:///home/shixuan/code/TechBrief/docs/delivery/Acceptance-Checklist.md)

### 2.2 运行形态

- 公开站点：`www.example.com`
- 后台管理：`admin.example.com`
- Web 框架：Django + Wagtail
- 异步任务：Celery + django-celery-beat + Redis
- 数据库：PostgreSQL
- 对象存储：腾讯云 COS

### 2.3 主要界面

- 公开站点：首页、列表页、详情页、Archive、About、Privacy、Terms
- 后台管理：登录页、仪表盘、来源管理、订阅者列表、内容列表 / 详情、工作流执行页、手动发布页

## 3. 接口与任务边界

### 3.1 HTTP 接口边界

- 公开页面：SSR 页面
- 公开 JSON API：`/api/public/*`
- 后台 JSON API：`/api/admin/*`
- 第三方回调：`/api/integrations/*`

### 3.2 关键能力

- 内容发现、抓取、抽取、翻译、研究报告、发布、邮件通知
- 来源启停与巡检配置
- 订阅 / 退订 / 每日汇总邮件
- 微信公众号手动草稿创建与重试
- 运行日志、失败重试、可观测性追踪

### 3.3 内部任务入口

- 定时 discover
- 手工触发 discover
- 手工触发指定阶段重试
- 手工触发每日汇总发送
- 历史内容回放验收

## 4. 配置与密钥

### 4.1 Django / 基础运行

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `REDIS_URL`
- `INITIAL_ADMIN_USERNAME`
- `INITIAL_ADMIN_PASSWORD`
- `INITIAL_ADMIN_EMAIL`

### 4.2 对象存储与站点

- `COS_SECRET_ID`
- `COS_SECRET_KEY`
- `COS_BUCKET`
- `COS_REGION`
- `PUBLIC_BASE_URL`
- `ADMIN_BASE_URL`
- `GA_MEASUREMENT_ID`

### 4.3 翻译服务

- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL`
- `MINIMAX_MODEL`
- `TRANSLATION_STYLE`
- `GLOSSARY_PATH`

### 4.4 ASR 服务（当前方案）

- `ASR_PROVIDER=mimo`
- `ASR_API_BASE_URL=https://api.xiaomimimo.com/v1`
- `MIMO_API_KEY`
- `ASR_MODEL=mimo-v2.5-asr`
- `ASR_LANGUAGE_DEFAULT=en`
- `ASR_TIMEOUT_SECONDS`
- `ASR_MAX_AUDIO_MINUTES`

### 4.5 邮件服务

- `EMAIL_PROVIDER=resend`
- `EMAIL_API_KEY`
- `EMAIL_FROM`
- `EMAIL_REPLY_TO`
- `EMAIL_MODE=mock|real`
- `EMAIL_DIGEST_SCHEDULE`

### 4.6 微信公众号（后台手动发布）

- `WECHAT_MODE=mock|real`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`

## 5. Mock 策略（无真实凭据场景）

### 5.1 邮件 mock

- 每日汇总邮件写入本地目录
- 保留收件人、主题、正文、批次 ID、内容列表
- 支持失败注入，验证重发与可追溯能力

### 5.2 微信草稿 mock

- 后台手动创建草稿时返回可追踪的 `wechat_draft_id`
- 草稿默认复用站内内容封面、摘要和作者信息
- 支持模拟接口错误码，验证后台重试流程

### 5.3 ASR mock

- 对无字幕视频可返回固定转录结果或失败响应
- 保留 `request_id`、音频时长、provider 响应摘要，便于验收转录链路

## 6. 建议交付顺序

1. 初始化 Django + Wagtail + Celery + PostgreSQL + Redis + COS 基座
2. 落来源、内容、订阅、工作流、发布记录等核心数据模型
3. 实现内容发现与抓取抽取链路
4. 接入翻译、ASR、邮件、微信等外部能力
5. 实现公开站点与后台管理界面
6. 完成回放验收、错误注入与交付说明

## 7. 验收回放流程（建议）

按 [Acceptance-Checklist.md](file:///home/shixuan/code/TechBrief/docs/delivery/Acceptance-Checklist.md) 逐项勾选：

1. 准备 10 条回放内容（OpenAI 5 条 + Anthropic 5 条），同时覆盖文章与公开视频资料
2. 运行回放流程，生成并校验：
   - 原始 HTML / 原始响应快照
   - 字幕文件或音频提取结果
   - 转录文字稿与可用的 provider 响应摘要
   - `content_ast` / `content_md`
   - `zh_ast` / `zh_md`
   - 深度研究报告
   - 公开站点预览页或正式发布页
   - 每日汇总邮件批次与投递记录
3. 抽样检查结构保真：标题层级、代码块数量、主要链接存在
4. 验证去重：对同一批 URL / source_id 重复执行，不产生第二份内容记录
5. 人为注入失败（抓取 / 转录 / 翻译 / 发布 / 邮件发送 / 微信草稿），验证：
   - 错误阶段与摘要可查询
   - 从失败点重试后成功
6. 通过后台完成：
   - 来源启停或手工触发巡检
   - 内容人工发布到 Web
   - 邮箱订阅与退订
   - 查看每日工作流执行记录
   - 验证每日汇总邮件内容
   - 手动创建微信公众号草稿

## 8. 交付判定

- 以 PRD、技术方案、数据库设计、API 设计、系统架构和验收清单为准
- 若实现行为与上述正式文档冲突，以最新版本正式文档优先
