# TechBrief

TechBrief 是一个面向 AI 技术内容的公开 Web 站点与后台管理系统方案仓库，当前仓库主要保存产品需求、技术方案、系统架构、数据库设计、API 设计和交付文档。

## 当前状态

- 当前仓库仍以文档为主，尚未开始实现正式工程代码
- 最新方案已经收敛为：
  - Django + Wagtail
  - Celery + django-celery-beat + Redis
  - PostgreSQL
  - 腾讯云 COS
  - Resend
  - mimo-v2.5-asr API

## 文档导航

### 核心方案

- [PRD](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md)
- [技术方案](file:///home/shixuan/code/TechBrief/docs/delivery/Technical-Solution-Report.md)
- [系统架构](file:///home/shixuan/code/TechBrief/docs/delivery/System-Architecture.md)
- [数据库设计](file:///home/shixuan/code/TechBrief/docs/delivery/Database-Design.md)
- [API 设计](file:///home/shixuan/code/TechBrief/docs/delivery/API-Design.md)

### 交付与验收

- [交付说明](file:///home/shixuan/code/TechBrief/docs/delivery/Delivery-Guide.md)
- [验收清单](file:///home/shixuan/code/TechBrief/docs/delivery/Acceptance-Checklist.md)

## MVP 范围

- 公开站点：首页、列表页、详情页、Archive、About、Privacy、Terms
- 后台管理：仪表盘、来源管理、订阅者、内容、工作流、手动发布
- 内容类型：文章 + 公开视频资料
- 核心流程：发现、抓取、抽取、转录、翻译、研究、审核、发布、邮件通知
- 邮件：直接订阅成功、退订、每日汇总
- 微信：后台手动创建草稿

## 说明

- 若不同文档之间出现歧义，以最新版本的 PRD、技术方案、数据库设计、API 设计为准
- 早期的阶段性审计与旧实施草案已移除，避免与当前正式方案冲突
