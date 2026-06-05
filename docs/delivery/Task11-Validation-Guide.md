# Task11 验证指南

更新时间：2026-06-05

## 1. 当前范围

- 当前文档以 `Task 11.1` 的自动化验证、手工验证脚本和 mock-first 回放样例为基础，同时补充 `Task 11.2 / 11.3` 的证据采集入口。
- 当前验证不宣称已经完成 10 条历史公开内容回放，也不宣称已经完成真实 Resend、微信、COS、ASR、GA4 联调。
- 当前验证报告只覆盖仓库内已实现的公开站点、后台骨架、工作流骨架、发布、订阅、每日汇总和微信草稿 mock 链路。

## 2. 自动化验证

执行一键脚本：

```bash
scripts/run_task11_automated_validation.sh
```

脚本会顺序执行：

1. `uv run python manage.py migrate --settings=techbrief.settings.test`
2. `uv run pytest tests/test_acceptance_validation.py tests/test_content_pipeline_workflow.py tests/test_publishers.py tests/test_public_site.py tests/test_admin_console.py`
3. `uv run python manage.py validate_acceptance_replays --settings=techbrief.settings.test --report-file artifacts/validation/task11_acceptance_report.json`

自动化报告当前会校验：

- OpenAI / Anthropic 两个来源均有回放样例
- `article` / `video` 两类内容均有回放样例
- `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending` 同步回放可达
- `publish -> notify -> wechat draft` mock-first 回放可达
- 标题层级、代码块数量、主要链接目标在原文和译文样例中保持一致
- 邮件部分失败不回滚 Web 发布
- 微信草稿失败不阻断 Web 发布

## 3. 手工验证准备

执行准备脚本：

```bash
scripts/run_task11_manual_validation_prep.sh
```

脚本会完成：

- 迁移测试设置数据库
- 装载 Wagtail 基础页面种子
- 生成一份最新的 mock-first 验收回放报告

随后按脚本输出继续执行：

```bash
uv run python manage.py runserver 127.0.0.1:8010 --settings=techbrief.settings.test
```

## 4. 手工检查点

- 公开站点：访问 `/`、`/articles`、`/about`、`/privacy`、`/terms`
- 详情页：打开一条已发布内容，检查中文正文、双语模式、来源链接和免责声明
- 订阅链路：调用 `/api/public/subscriptions`，再访问 `/unsubscribe/<token>`
- 后台入口：访问 `/cms/` 登录页和 `/cms/techbrief/` 后台壳层
- 后台页面：检查 dashboard、content、subscribers、workflow 页面是否可访问
- 验收报告：确认 `artifacts/validation/*.json` 中的 criteria 全部通过，且 limitations 仍明确记录未覆盖项

## 5. 当前限制

- 目前只有 4 条 mock-first 回放样例，不等价于验收清单要求的 10 条历史公开内容回放
- 当前结构保真检查只验证标题层级、代码块数量、链接目标，不等价于完整 AST 保真验收
- 当前已可通过 `uv run python manage.py generate_task11_evidence --settings=techbrief.settings.test` 生成 `docs/validation/task11/report.json`、`summary.md` 和 HTML / JSON / run log / publish record 样本
- 当前环境仍无法产出浏览器截图，且尚未沉淀 COS 对象键、第三方回调 payload 或真实外部联调证据
