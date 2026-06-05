# Task 11 验收验证与证据汇总

- 生成时间: 2026-06-05T09:28:53.707922+00:00
- 执行命令: `python manage.py generate_task11_evidence --settings=techbrief.settings.test`
- Public Base URL: `http://127.0.0.1:8010`
- Admin Base URL: `http://127.0.0.1:8010`

## 已验证链路

- 公开站点: 首页、列表页、Archive、详情页、About、Privacy、Terms、退订结果页。
- 订阅链路: 订阅、同幂等键重放、退订 API 与退订结果页。
- 后台链路: 登录后仪表盘、内容列表、订阅者列表、工作流页及对应 API。
- 流水线链路: `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending` mock 回放。
- 发布链路: Web 发布、digest 邮件发送、微信草稿创建 mock 回放。
- 运行证据: HTML 样本、API 返回、run log 摘要、发布记录、digest 投递记录。

## 未覆盖或受限项

- 当前命令未执行 Resend、微信、COS、ASR、GA4 的真实外部联调。
- 当前环境未集成浏览器截图能力，因此未产出新的页面截图。
- 当前证据以 mock 适配器与本地测试设置为主，用于回归验证与验收留痕，不等同于上线联调完成。

## 证据文件

- `report.json`
- `samples/admin-content.json`
- `samples/admin-dashboard.html`
- `samples/admin-dashboard.json`
- `samples/admin-subscribers.json`
- `samples/admin-workflow.json`
- `samples/pipeline-discovery.json`
- `samples/pipeline-run-logs.json`
- `samples/public-archive.html`
- `samples/public-article-detail.html`
- `samples/public-articles.html`
- `samples/public-content-item-detail.json`
- `samples/public-content-items.json`
- `samples/public-home.html`
- `samples/publish-notify-wechat.json`
- `samples/subscription-create.json`
- `samples/subscription-unsubscribe.json`
