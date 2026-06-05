# TechBrief API 设计文档

更新时间：2026-06-04

## 1. 文档目标

本文档基于以下输入统一设计 TechBrief 的接口体系：

- [TechBrief-PRD.md](file:///home/shixuan/code/TechBrief/TechBrief-PRD.md)
- [Technical-Solution-Report.md](file:///home/shixuan/code/TechBrief/docs/delivery/Technical-Solution-Report.md)
- 原型目录 `stitch_ai_insight_bridge` 中全部前台 / 后台页面

目标是覆盖项目全部业务功能，形成一套可直接用于后端实现与前后端联调的接口规范。

## 2. 总体约定

### 2.1 域名与接口分区

| 域名/前缀                       | 用途                       |
| --------------------------- | ------------------------ |
| `https://www.example.com`   | 公开站点 SSR 页面与公开 JSON API  |
| `https://admin.example.com` | 后台管理 SSR 页面与管理员 JSON API |
| `/api/public/*`             | 公开 JSON API              |
| `/api/admin/*`              | 后台 JSON API              |
| `/api/integrations/*`       | 第三方回调接口                  |

### 2.2 认证方式

- 公开页面与公开内容 API：无需登录
- 后台页面与后台 API：基于 **Django Session + HttpOnly Cookie** 登录态认证
- 后台写操作：必须校验 **CSRF Token**
- 当前项目为单管理员或少量管理员模式，不设计复杂 RBAC

### 2.3 公共请求头

| Header                           | 必填          | 说明                                |
| -------------------------------- | ----------- | --------------------------------- |
| `Content-Type: application/json` | JSON 请求必填   | JSON 请求体                          |
| `Accept-Language`                | 公开 API 建议传递 | 默认取浏览器系统语言；命中简体中文时返回中文内容，否则返回英文内容 |
| `X-Request-ID`                   | 否           | 客户端可传；若不传由服务端生成                   |
| `Idempotency-Key`                | 部分 POST 必填  | 用于订阅、导入、发布、发送等幂等场景                |
| `X-CSRFToken`                    | 后台写接口必填     | Django CSRF 校验                    |

### 2.4 统一 JSON 返回结构

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {},
  "meta": {
    "request_id": "req_01JXYZ...",
    "run_id": "run_01JXYZ..."
  }
}
```

失败返回：

```json
{
  "success": false,
  "code": "CONTENT_NOT_FOUND",
  "message": "content item not found",
  "data": null,
  "error": {
    "type": "NotFoundError",
    "details": {
      "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc"
    }
  },
  "meta": {
    "request_id": "req_01JXYZ..."
  }
}
```

### 2.5 分页约定

列表接口统一使用：

- `page`：页码，从 `1` 开始
- `page_size`：分页大小，默认 `20`，最大 `100`

列表返回示例：

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 120,
      "total_pages": 6
    }
  },
  "meta": {
    "request_id": "req_01JXYZ..."
  }
}
```

### 2.6 幂等性约定

以下接口要求客户端传 `Idempotency-Key`：

- 订阅创建
- 手动 URL 导入
- 纯手工内容创建
- 手工启动翻译
- Web 发布
- 微信草稿创建 / 重试
- 每日汇总发送

服务端以 `Idempotency-Key + operator_scope + action` 建立幂等记录，重复请求返回首次成功结果或当前任务状态。

### 2.7 语言协商约定

- 公开 JSON API 的返回语言只根据 `Accept-Language` 协商
- 未传 `Accept-Language` 时，服务端按浏览器系统语言或服务端默认配置处理，默认回退 `en-US`
- 命中 `zh-CN`、`zh-Hans`、`zh-SG` 等简体中文标识时返回中文内容，其余语言默认返回英文内容
- 公开 SSR 页面优先读取 `tb_locale` Cookie 作为用户手动切换后的站点语言偏好；未命中时再读取 `Accept-Language`
- `tb_locale` 当前支持 `zh-CN`、`en-US`，建议有效期 `30` 天
- 首页、列表页、Archive、静态页等运营文案在数据层采用中英双字段存储，SSR 按当前语言偏好选择对应字段返回
- 首页、列表页、Archive、静态页和详情页的导航、页头、页脚文案遵循上述页面语言规则
- 详情页正文阅读布局仍由 `view=zh|bilingual` 控制；该参数只决定正文展示模式，不替代语言协商
- 该偏好仅用于 SSR 页面与公开接口输出，无需单独落库

## 3. 页面路由（SSR）

> 页面路由返回 `text/html`，不使用统一 JSON envelope；其配套交互由下文 JSON API 提供。

### 3.1 公开站点页面

| 名称      | 方法  | 路径                               | 功能                | 查询参数                                                     | 权限          | <br /> |
| ------- | --- | -------------------------------- | ----------------- | -------------------------------------------------------- | ----------- | :----- |
| 首页      | GET | `/`                              | 展示 Hero、精选内容、订阅入口 | 无                                                        | 公开          | <br /> |
| 列表页     | GET | `/articles`                      | 内容列表与筛选           | `source`、`content_type`、`date_from`、`date_to`、`q`、`page` | 公开          | <br /> |
| Archive | GET | `/archive`                       | 历史归档视图            | `year`、`month`、`page`                                    | 公开          | <br /> |
| 文章详情页   | GET | `/articles/{slug}`               | 文章详情页             | \`view=zh                                                | bilingual\` | 公开     |
| 视频详情页   | GET | `/videos/{slug}`                 | 视频详情页             | \`view=zh                                                | bilingual\` | 公开     |
| About   | GET | `/about`                         | 静态页               | 无                                                        | 公开          | <br /> |
| Privacy | GET | `/privacy`                       | 静态页               | 无                                                        | 公开          | <br /> |
| Terms   | GET | `/terms`                         | 静态页               | 无                                                        | 公开          | <br /> |
| 退订确认页   | GET | `/unsubscribe/{token}`           | 展示退订确认结果页         | 无                                                        | 公开          | <br /> |

### 3.2 后台页面

| 名称    | 方法  | 路径             | 功能         | 权限  |
| ----- | --- | -------------- | ---------- | --- |
| 登录页   | GET | `/login`       | 管理员登录页     | 公开  |
| 仪表盘   | GET | `/dashboard`   | 后台概览页      | 管理员 |
| 内容管理  | GET | `/articles`    | 内容管理页      | 管理员 |
| 订阅管理  | GET | `/subscribers` | 订阅者管理页     | 管理员 |
| 工作流监控 | GET | `/workflow`    | 运行监控页      | 管理员 |
| 手动发布  | GET | `/publishing`  | 手动导入与微信发布页 | 管理员 |

## 4. 公开 JSON API

### 4.1 获取公开内容列表

- **名称**：获取公开内容列表
- **方法**：`GET`
- **路径**：`/api/public/content-items`
- **功能描述**：为公开列表页和 Archive 提供可筛选的内容数据。
- **权限**：公开
- **幂等性**：天然幂等

**查询参数**

| 参数             | 必填 | 类型           | 说明                               |
| -------------- | -- | ------------ | -------------------------------- |
| `page`         | 否  | integer      | 页码，默认 1                          |
| `page_size`    | 否  | integer      | 每页数量，默认 20，最大 100                |
| `source`       | 否  | string       | 来源编码，如 `openai`、`anthropic`      |
| `content_type` | 否  | string       | `article`、`video`                |
| `date_from`    | 否  | string(date) | 开始日期                             |
| `date_to`      | 否  | string(date) | 结束日期                             |
| `q`            | 否  | string       | 标题模糊搜索                           |
| `sort`         | 否  | string       | `published_desc`、`published_asc` |

**返回结构**

| 字段                                | 类型               | 说明      |
| --------------------------------- | ---------------- | ------- |
| `data.items[]`                    | array<object>    | 内容列表    |
| `data.items[].id`                 | string(uuid)     | 内容 ID   |
| `data.items[].slug`               | string           | 公开 slug |
| `data.items[].content_type`       | string           | 内容类型    |
| `data.items[].source_name`        | string           | 来源名称    |
| `data.items[].title_zh`           | string           | 中文标题    |
| `data.items[].summary_zh`         | string           | 中文摘要    |
| `data.items[].cover_url`          | string/null      | 封面图 URL |
| `data.items[].published_at`       | string(datetime) | 来源发布时间  |
| `data.items[].reading_mode_flags` | object           | 阅读模式支持  |
| `data.pagination`                 | object           | 分页信息    |

**调用示例**

```http
GET /api/public/content-items?page=1&page_size=20&source=openai&content_type=article HTTP/1.1
Host: www.example.com
```

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
        "slug": "openai-o1-reasoning-era",
        "content_type": "article",
        "source_name": "OpenAI",
        "title_zh": "OpenAI o1 模型：开启推理新纪元",
        "summary_zh": "解析推理模型如何在复杂任务中获得更高质量输出。",
        "cover_url": "https://cos.example.com/techbrief/prod/content-items/.../media/cover/original.webp",
        "published_at": "2026-06-03T10:00:00Z",
        "reading_mode_flags": {
          "supports_bilingual": true
        }
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "meta": {
    "request_id": "req_public_list_001"
  }
}
```

**错误码**

- `VALIDATION_INVALID_QUERY`
- `SYSTEM_INTERNAL_ERROR`

***

### 4.2 获取公开内容详情

- **名称**：获取公开内容详情
- **方法**：`GET`
- **路径**：`/api/public/content-items/{slug}`
- **功能描述**：提供详情页渲染和中英双语阅读所需数据。
- **权限**：公开
- **幂等性**：天然幂等

**路径参数**

| 参数     | 必填 | 类型     | 说明         |
| ------ | -- | ------ | ---------- |
| `slug` | 是  | string | 公开详情页 slug |

**查询参数**

| 参数     | 必填 | 类型     | 说明                 |
| ------ | -- | ------ | ------------------ |
| `view` | 否  | string | `zh` 或 `bilingual` |

**返回结构**

| 字段                             | 类型               | 说明        |
| ------------------------------ | ---------------- | --------- |
| `data.id`                      | string(uuid)     | 内容 ID     |
| `data.slug`                    | string           | slug      |
| `data.content_type`            | string           | 内容类型      |
| `data.source_name`             | string           | 来源名称      |
| `data.title_zh`                | string           | 中文标题      |
| `data.title_original`          | string           | 原始标题      |
| `data.author_or_speaker`       | string/null      | 作者 / 讲者   |
| `data.published_at_source`     | string(datetime) | 来源发布时间    |
| `data.source_url`              | string/null      | 原始来源地址    |
| `data.cover_url`               | string/null      | 封面图地址     |
| `data.view_mode`               | string           | 实际返回的阅读模式 |
| `data.content_blocks_zh`       | array<object>    | 中文结构块     |
| `data.content_blocks_original` | array<object>    | 原文结构块     |
| `data.research_report_md`      | string/null      | 研究报告      |
| `data.disclaimer`              | string           | 文末声明      |

**调用示例**

```http
GET /api/public/content-items/openai-o1-reasoning-era?view=bilingual HTTP/1.1
Host: www.example.com
```

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
    "slug": "openai-o1-reasoning-era",
    "content_type": "article",
    "source_name": "OpenAI",
    "title_zh": "OpenAI o1 模型：开启推理新纪元",
    "title_original": "OpenAI o1 Model: Ushering in a New Era of Reasoning",
    "author_or_speaker": "OpenAI",
    "published_at_source": "2026-06-03T10:00:00Z",
    "source_url": "https://openai.com/index/openai-o1/",
    "cover_url": "https://cos.example.com/.../cover.webp",
    "view_mode": "bilingual",
    "content_blocks_zh": [
      {"type": "paragraph", "text": "我们推出了一系列新的 AI 模型..."}
    ],
    "content_blocks_original": [
      {"type": "paragraph", "text": "We are introducing a new series of AI models..."}
    ],
    "research_report_md": null,
    "disclaimer": "本文为公开英文内容的中文整理 / 翻译版本。"
  },
  "meta": {
    "request_id": "req_public_detail_001"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `CONTENT_NOT_PUBLISHED`
- `VALIDATION_INVALID_QUERY`
- `SYSTEM_INTERNAL_ERROR`

***

### 4.3 创建订阅

- **名称**：创建邮箱订阅
- **方法**：`POST`
- **路径**：`/api/public/subscriptions`
- **功能描述**：公开站点订阅入口，支持 Hero、导航、悬浮 CTA、弹窗提交。
- **权限**：公开
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数            | 必填 | 类型            | 说明                                                                       |
| ------------- | -- | ------------- | ------------------------------------------------------------------------ |
| `email`       | 是  | string(email) | 订阅邮箱                                                                     |
| `source_page` | 是  | string        | 来源页面：`home_hero`、`nav_modal`、`subscription_modal`、`article_floating_cta` |
| `locale`      | 否  | string        | 订阅偏好语言；不传则服务端根据 `Accept-Language` 推断，简体中文记为 `zh-CN`，其他语言记为 `en-US`       |

**请求示例**

```json
{
  "email": "reader@example.com",
  "source_page": "article_floating_cta",
  "locale": "zh-CN"
}
```

**返回结构**

| 字段                           | 类型                    | 说明                                                  |
| ---------------------------- | --------------------- | --------------------------------------------------- |
| `data.subscriber_id`         | string(uuid)          | 订阅者 ID                                              |
| `data.status`                | string                | 订阅状态，固定为 `active`                                   |
| `data.subscribed_at`         | string(datetime)      | 订阅时间                                                |
| `data.unsubscribe_token`     | string                | 退订 token，用于生成邮件内退订链接                                |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "subscription created",
  "data": {
    "subscriber_id": "1a34f8c6-2d3d-43ef-b9ab-6c5d4430cefe",
    "status": "active",
    "subscribed_at": "2026-06-04T08:20:10Z",
    "unsubscribe_token": "unsub_tok_xxxxxxxxx"
  },
  "meta": {
    "request_id": "req_subscribe_001"
  }
}
```

**错误码**

- `VALIDATION_INVALID_EMAIL`
- `SUBSCRIPTION_ALREADY_ACTIVE`
- `SUBSCRIPTION_ALREADY_UNSUBSCRIBED`
- `SYSTEM_INTERNAL_ERROR`

***

### 4.4 退订

- **名称**：执行退订
- **方法**：`POST`
- **路径**：`/api/public/subscriptions/unsubscribe`
- **功能描述**：通过退订 token 将订阅者状态改为 `unsubscribed`。
- **权限**：公开
- **幂等性**：天然幂等，重复退订返回当前状态

**请求体参数**

| 参数      | 必填 | 类型     | 说明       |
| ------- | -- | ------ | -------- |
| `token` | 是  | string | 退订 token |

**请求示例**

```json
{
  "token": "unsub_tok_xxxxxxxxx"
}
```

**返回结构**

| 字段                     | 类型               | 说明                        |
| ---------------------- | ---------------- | ------------------------- |
| `data.status`          | string           | 当前订阅状态，固定为 `unsubscribed` |
| `data.unsubscribed_at` | string(datetime) | 退订生效时间                    |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "unsubscribed",
  "data": {
    "status": "unsubscribed",
    "unsubscribed_at": "2026-06-04T09:00:00Z"
  },
  "meta": {
    "request_id": "req_unsub_001"
  }
}
```

**错误码**

- `SUBSCRIPTION_TOKEN_INVALID`
- `SYSTEM_INTERNAL_ERROR`

## 5. 后台认证 API

### 5.1 管理员登录

- **方法**：`POST`
- **路径**：`/api/admin/auth/login`
- **功能描述**：管理员账号密码登录，成功后写入 Session Cookie。
- **权限**：公开
- **幂等性**：不要求

**请求体参数**

| 参数         | 必填 | 类型     | 说明     |
| ---------- | -- | ------ | ------ |
| `username` | 是  | string | 管理员用户名 |
| `password` | 是  | string | 管理员密码  |

**返回结构**

| 字段                       | 类型           | 说明        |
| ------------------------ | ------------ | --------- |
| `data.user`              | object       | 当前登录管理员信息 |
| `data.user.id`           | string(uuid) | 管理员 ID    |
| `data.user.username`     | string       | 登录名       |
| `data.user.display_name` | string       | 展示名       |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "login success",
  "data": {
    "user": {
      "id": "989ab9d3-6c5e-4b02-bcc2-d91c05fd4e2f",
      "username": "admin",
      "display_name": "Admin"
    }
  },
  "meta": {
    "request_id": "req_login_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_ACCOUNT_DISABLED`

***

### 5.2 获取当前管理员

- **方法**：`GET`
- **路径**：`/api/admin/auth/me`
- **功能描述**：返回当前登录管理员信息。
- **权限**：管理员
- **幂等性**：天然幂等

**返回结构**

| 字段                            | 类型           | 说明        |
| ----------------------------- | ------------ | --------- |
| `data.user`                   | object       | 当前登录管理员信息 |
| `data.user.id`                | string(uuid) | 管理员 ID    |
| `data.user.is_platform_admin` | boolean      | 固定后台管理员标识 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "user": {
      "id": "989ab9d3-6c5e-4b02-bcc2-d91c05fd4e2f",
      "username": "admin",
      "display_name": "Admin",
      "is_platform_admin": true
    }
  },
  "meta": {
    "request_id": "req_me_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 5.3 管理员登出

- **方法**：`POST`
- **路径**：`/api/admin/auth/logout`
- **功能描述**：清除 Session 登录态。
- **权限**：管理员
- **幂等性**：天然幂等

**返回结构**

| 字段     | 类型   | 说明           |
| ------ | ---- | ------------ |
| `data` | null | 无返回体，仅表示登出成功 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "logout success",
  "data": null,
  "meta": {
    "request_id": "req_logout_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

## 6. 后台仪表盘与订阅管理 API

### 6.1 获取仪表盘概览

- **方法**：`GET`
- **路径**：`/api/admin/dashboard`
- **功能描述**：返回仪表盘指标卡、最近动态和系统状态摘要。
- **权限**：管理员
- **幂等性**：天然幂等

**查询参数**

| 参数     | 必填 | 类型           | 说明   |
| ------ | -- | ------------ | ---- |
| `date` | 否  | string(date) | 默认当天 |

**返回结构**

| 字段                         | 类型            | 说明     |
| -------------------------- | ------------- | ------ |
| `data.metrics`             | object        | 关键指标   |
| `data.recent_activities[]` | array<object> | 最近动态   |
| `data.system_status`       | object        | 系统状态摘要 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "metrics": {
      "new_content_today": 12,
      "published_today": 5,
      "failed_today": 1,
      "subscriber_new_today": 34,
      "subscriber_total": 12458,
      "review_pending_count": 9,
      "workflow_success_rate": 0.9167
    },
    "recent_activities": [
      {
        "type": "content_discovered",
        "message": "新文章自动抓取成功",
        "occurred_at": "2026-06-04T08:10:00Z",
        "target_type": "content_item",
        "target_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc"
      }
    ],
    "system_status": {
      "database": "online",
      "redis": "online",
      "worker": "online"
    }
  },
  "meta": {
    "request_id": "req_dashboard_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`
- `SYSTEM_INTERNAL_ERROR`

***

### 6.2 获取订阅者列表

- **方法**：`GET`
- **路径**：`/api/admin/subscribers`
- **功能描述**：订阅者列表、搜索、排序、状态筛选。
- **权限**：管理员
- **幂等性**：天然幂等

**查询参数**

| 参数          | 必填 | 类型      | 说明                                                                    |
| ----------- | -- | ------- | --------------------------------------------------------------------- |
| `page`      | 否  | integer | 页码                                                                    |
| `page_size` | 否  | integer | 每页大小                                                                  |
| `q`         | 否  | string  | 邮箱搜索                                                                  |
| `status`    | 否  | string  | `active`、`unsubscribed`、`bounced`、`complained` |
| `sort`      | 否  | string  | `subscribed_desc`、`subscribed_asc`                                    |

**返回结构**

| 字段                         | 类型            | 说明     |
| -------------------------- | ------------- | ------ |
| `data.items[]`             | array<object> | 订阅者列表  |
| `data.items[].email`       | string        | 订阅邮箱   |
| `data.items[].status`      | string        | 当前订阅状态 |
| `data.items[].source_page` | string        | 提交来源   |
| `data.pagination`          | object        | 分页信息   |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "1a34f8c6-2d3d-43ef-b9ab-6c5d4430cefe",
        "email": "reader@example.com",
        "status": "active",
        "source_page": "home_hero",
        "subscribed_at": "2026-06-04T08:20:10Z",
        "unsubscribed_at": null,
        "last_sent_at": "2026-06-04T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "meta": {
    "request_id": "req_admin_subscribers_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 6.3 修改订阅者状态

- **方法**：`PATCH`
- **路径**：`/api/admin/subscribers/{subscriber_id}/status`
- **功能描述**：管理员手工将订阅者标记为 `active` / `unsubscribed`。
- **权限**：管理员
- **幂等性**：同状态重复修改天然幂等

**路径参数**

| 参数              | 必填 | 类型           | 说明     |
| --------------- | -- | ------------ | ------ |
| `subscriber_id` | 是  | string(uuid) | 订阅者 ID |

**请求体参数**

| 参数       | 必填 | 类型     | 说明                      |
| -------- | -- | ------ | ----------------------- |
| `status` | 是  | string | `active`、`unsubscribed` |
| `reason` | 否  | string | 管理员备注                   |

**返回结构**

| 字段                | 类型               | 说明     |
| ----------------- | ---------------- | ------ |
| `data.id`         | string(uuid)     | 订阅者 ID |
| `data.status`     | string           | 最新状态   |
| `data.updated_at` | string(datetime) | 状态更新时间 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "subscriber status updated",
  "data": {
    "id": "1a34f8c6-2d3d-43ef-b9ab-6c5d4430cefe",
    "status": "unsubscribed",
    "updated_at": "2026-06-04T11:20:00Z"
  },
  "meta": {
    "request_id": "req_subscriber_status_001"
  }
}
```

**错误码**

- `SUBSCRIBER_NOT_FOUND`
- `SUBSCRIPTION_STATUS_CONFLICT`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 6.4 获取来源列表

- **方法**：`GET`
- **路径**：`/api/admin/sources`
- **功能描述**：返回来源主数据、启停状态、调度配置和发现入口，用于来源管理与手工巡检范围选择。
- **权限**：管理员
- **幂等性**：天然幂等

**查询参数**

| 参数            | 必填 | 类型      | 说明                                                |
| ------------- | -- | ------- | ------------------------------------------------- |
| `is_enabled`  | 否  | boolean | 按启用状态过滤                                           |
| `source_type` | 否  | string  | `official_site`、`video_channel`、`manual_external` |

**返回结构**

| 字段                                | 类型            | 说明     |
| --------------------------------- | ------------- | ------ |
| `data.items[]`                    | array<object> | 来源列表   |
| `data.items[].id`                 | string(uuid)  | 来源 ID  |
| `data.items[].source_code`        | string        | 来源编码   |
| `data.items[].source_name`        | string        | 来源展示名称 |
| `data.items[].is_enabled`         | boolean       | 是否启用   |
| `data.items[].schedule_cron_expr` | string        | 调度表达式  |
| `data.items[].endpoints[]`        | array<object> | 发现入口列表 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "9f39d6dd-58d6-4694-93ef-368c93e2bc3f",
        "source_code": "openai",
        "source_name": "OpenAI",
        "source_type": "official_site",
        "is_enabled": true,
        "schedule_cron_expr": "0 2 * * *",
        "endpoints": [
          {
            "id": "9bf4cd58-2ad2-4984-8a57-f1e3b014da21",
            "endpoint_type": "rss",
            "endpoint_url": "https://openai.com/news/rss.xml",
            "is_enabled": true
          }
        ]
      }
    ]
  },
  "meta": {
    "request_id": "req_sources_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 6.5 更新来源配置

- **方法**：`PATCH`
- **路径**：`/api/admin/sources/{source_id}`
- **功能描述**：更新来源启停、调度表达式、备注和入口启停状态。
- **权限**：管理员
- **幂等性**：按资源更新幂等

**路径参数**

| 参数          | 必填 | 类型           | 说明    |
| ----------- | -- | ------------ | ----- |
| `source_id` | 是  | string(uuid) | 来源 ID |

**请求体参数（可选字段）**

| 参数                       | 必填 | 类型            | 说明       |
| ------------------------ | -- | ------------- | -------- |
| `is_enabled`             | 否  | boolean       | 是否启用该来源  |
| `schedule_cron_expr`     | 否  | string        | Cron 表达式 |
| `notes`                  | 否  | string        | 管理备注     |
| `endpoints[]`            | 否  | array<object> | 入口配置批量更新 |
| `endpoints[].id`         | 是  | string(uuid)  | 入口 ID    |
| `endpoints[].is_enabled` | 否  | boolean       | 是否启用入口   |
| `endpoints[].priority`   | 否  | integer       | 执行优先级    |

**返回结构**

| 字段                        | 类型               | 说明        |
| ------------------------- | ---------------- | --------- |
| `data.id`                 | string(uuid)     | 来源 ID     |
| `data.is_enabled`         | boolean          | 更新后的启停状态  |
| `data.schedule_cron_expr` | string           | 更新后的调度表达式 |
| `data.updated_at`         | string(datetime) | 更新时间      |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "source updated",
  "data": {
    "id": "9f39d6dd-58d6-4694-93ef-368c93e2bc3f",
    "is_enabled": true,
    "schedule_cron_expr": "0 2 * * *",
    "updated_at": "2026-06-04T11:32:00Z"
  },
  "meta": {
    "request_id": "req_source_update_001"
  }
}
```

**错误码**

- `SOURCE_NOT_FOUND`
- `VALIDATION_INVALID_BODY`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

## 7. 内容管理 API

### 7.1 获取内容列表

- **方法**：`GET`
- **路径**：`/api/admin/content-items`
- **功能描述**：后台内容列表，支持搜索、筛选、排序、状态徽标与快捷操作。
- **权限**：管理员
- **幂等性**：天然幂等

**查询参数**

| 参数             | 必填 | 类型           | 说明                                           |
| -------------- | -- | ------------ | -------------------------------------------- |
| `page`         | 否  | integer      | 页码                                           |
| `page_size`    | 否  | integer      | 每页大小                                         |
| `q`            | 否  | string       | 标题 / slug / URL 搜索                           |
| `status`       | 否  | string       | 内容状态                                         |
| `content_type` | 否  | string       | `article`、`video`、`manual`                   |
| `source_id`    | 否  | string(uuid) | 来源 ID                                        |
| `sort`         | 否  | string       | `published_desc`、`updated_desc`、`status_asc` |

**返回结构**

| 字段                                 | 类型            | 说明             |
| ---------------------------------- | ------------- | -------------- |
| `data.items[]`                     | array<object> | 内容列表           |
| `data.items[].id`                  | string(uuid)  | 内容 ID          |
| `data.items[].status`              | string        | 当前状态           |
| `data.items[].current_stage`       | string        | 当前阶段           |
| `data.items[].preview_url`         | string        | 后台预览地址         |
| `data.items[].available_actions[]` | array<string> | 前端可直接渲染的快捷操作集合 |
| `data.pagination`                  | object        | 分页信息           |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
        "content_type": "article",
        "source_name": "OpenAI",
        "title_original": "The Future of AI Design Systems",
        "title_zh": null,
        "status": "processing",
        "current_stage": "translate",
        "published_at_source": "2026-06-03T10:00:00Z",
        "preview_url": "https://admin.example.com/preview/content/c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
        "available_actions": [
          "view_detail",
          "retry_translate"
        ]
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "meta": {
    "request_id": "req_admin_contents_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`
- `VALIDATION_INVALID_QUERY`

***

### 7.2 获取内容详情

- **方法**：`GET`
- **路径**：`/api/admin/content-items/{content_item_id}`
- **功能描述**：返回原文、译文、研究报告、对象文件、运行记录、错误日志、渲染预览信息。
- **权限**：管理员
- **幂等性**：天然幂等

**路径参数**

| 参数                | 必填 | 类型           | 说明    |
| ----------------- | -- | ------------ | ----- |
| `content_item_id` | 是  | string(uuid) | 内容 ID |

**返回结构（核心字段）**

| 字段                       | 类型            | 说明       |
| ------------------------ | ------------- | -------- |
| `data.content`           | object        | 内容主信息    |
| `data.artifacts[]`       | array<object> | 关联对象存储文件 |
| `data.run_logs[]`        | array<object> | 阶段运行记录   |
| `data.publish_records[]` | array<object> | 发布记录     |
| `data.preview`           | object        | 公开页预览    |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "content": {
      "id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
      "content_type": "article",
      "status": "review_pending",
      "current_stage": "review_pending",
      "source_name": "OpenAI",
      "title_original": "The Future of AI Design Systems",
      "title_zh": "AI 设计系统的未来",
      "summary_zh": "聚焦模型与产品设计协同演进。",
      "zh_md": "# AI 设计系统的未来",
      "research_report_md": "## Research Notes",
      "supports_bilingual": true
    },
    "artifacts": [
      {
        "artifact_type": "raw_html",
        "storage_key": "techbrief/prod/content-items/c1/raw/raw.html"
      }
    ],
    "run_logs": [
      {
        "stage": "translate",
        "status": "success",
        "duration_ms": 18234
      }
    ],
    "publish_records": [],
    "preview": {
      "mode": "admin_protected",
      "url": "https://admin.example.com/preview/content/c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc"
    }
  },
  "meta": {
    "request_id": "req_content_detail_001"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

### 7.3 手动 URL 导入

- **方法**：`POST`
- **路径**：`/api/admin/content-items/import-url`
- **功能描述**：管理员输入 URL，创建待处理内容并触发抓取/抽取/翻译链路。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数               | 必填 | 类型           | 说明                    |
| ---------------- | -- | ------------ | --------------------- |
| `url`            | 是  | string(uri)  | 要导入的文章 URL            |
| `source_id`      | 否  | string(uuid) | 若已知来源，传来源 ID；用于后台来源选择 |
| `source_name`    | 否  | string       | 手工指定来源名称              |
| `force_reimport` | 否  | boolean      | 是否忽略已存在内容重新入队         |

**返回结构**

| 字段                     | 类型           | 说明          |
| ---------------------- | ------------ | ----------- |
| `data.content_item_id` | string(uuid) | 新建或复用的内容 ID |
| `data.status`          | string       | 当前内容状态      |
| `data.current_stage`   | string       | 当前阶段        |
| `data.run_id`          | string(uuid) | 本次异步任务运行 ID |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "content import queued",
  "data": {
    "content_item_id": "a92d4bd6-2e08-4f02-a8e7-4176a76b9be1",
    "status": "processing",
    "current_stage": "fetch",
    "run_id": "1bbf31c8-ef59-47c2-a14a-b4372e9f2ffb"
  },
  "meta": {
    "request_id": "req_import_url_001",
    "run_id": "1bbf31c8-ef59-47c2-a14a-b4372e9f2ffb"
  }
}
```

**错误码**

- `VALIDATION_INVALID_URL`
- `CONTENT_ALREADY_EXISTS`
- `PIPELINE_FETCH_FAILED`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 7.4 纯手工创建内容

- **方法**：`POST`
- **路径**：`/api/admin/content-items/manual`
- **功能描述**：手工录入标题、摘要、原文、译文和来源信息，直接进入审核流。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数                    | 必填 | 类型               | 说明                   |
| --------------------- | -- | ---------------- | -------------------- |
| `content_type`        | 是  | string           | `article` 或 `manual` |
| `source_id`           | 否  | string(uuid)     | 已配置来源 ID；手工录入来源时可为空  |
| `source_name`         | 是  | string           | 来源名称                 |
| `title_original`      | 是  | string           | 原文标题                 |
| `title_zh`            | 是  | string           | 中文标题                 |
| `summary_original`    | 否  | string           | 原文摘要                 |
| `summary_zh`          | 否  | string           | 中文摘要                 |
| `body_original_md`    | 是  | string           | 原文 Markdown          |
| `body_zh_md`          | 是  | string           | 中文 Markdown          |
| `canonical_url`       | 否  | string(uri)      | 原始来源链接               |
| `published_at_source` | 否  | string(datetime) | 来源发布时间               |
| `author_or_speaker`   | 否  | string           | 作者 / 讲者              |

**返回结构**

| 字段                     | 类型           | 说明                             |
| ---------------------- | ------------ | ------------------------------ |
| `data.content_item_id` | string(uuid) | 新建内容 ID                        |
| `data.status`          | string       | 当前状态                           |
| `data.current_stage`   | string       | 当前阶段，纯手工录入默认为 `review_pending` |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "manual content created",
  "data": {
    "content_item_id": "b4113c6f-b9a1-4315-bfe4-6487660a5821",
    "status": "review_pending",
    "current_stage": "review_pending"
  },
  "meta": {
    "request_id": "req_manual_content_001"
  }
}
```

**错误码**

- `VALIDATION_REQUIRED_FIELD_MISSING`
- `VALIDATION_INVALID_BODY`
- `CONTENT_STATUS_CONFLICT`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 7.5 更新内容草稿

- **方法**：`PATCH`
- **路径**：`/api/admin/content-items/{content_item_id}`
- **功能描述**：管理员编辑标题、摘要、译文、研究报告、阅读模式配置等。
- **权限**：管理员
- **幂等性**：按资源更新幂等

**请求体参数（可选字段）**

| 参数                   | 必填 | 类型      | 说明                                      |
| -------------------- | -- | ------- | --------------------------------------- |
| `title_zh`           | 否  | string  | 中文标题                                    |
| `summary_zh`         | 否  | string  | 中文摘要                                    |
| `zh_md`              | 否  | string  | 中文 Markdown                             |
| `research_report_md` | 否  | string  | 深度研究报告                                  |
| `supports_bilingual` | 否  | boolean | 是否支持双语对照                                |
| `status`             | 否  | string  | 允许从 `failed` / `review_pending` 调整到目标状态 |

**返回结构**

| 字段                     | 类型               | 说明     |
| ---------------------- | ---------------- | ------ |
| `data.content_item_id` | string(uuid)     | 内容 ID  |
| `data.status`          | string           | 更新后的状态 |
| `data.updated_at`      | string(datetime) | 更新时间   |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "content updated",
  "data": {
    "content_item_id": "b4113c6f-b9a1-4315-bfe4-6487660a5821",
    "status": "review_pending",
    "updated_at": "2026-06-04T12:08:00Z"
  },
  "meta": {
    "request_id": "req_content_patch_001"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `CONTENT_STATUS_CONFLICT`
- `VALIDATION_INVALID_BODY`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 7.6 启动翻译

- **方法**：`POST`
- **路径**：`/api/admin/content-items/{content_item_id}/translate`
- **功能描述**：对 Draft 或导入内容手工触发翻译任务。
- **权限**：管理员
- **幂等性**：同一 `Idempotency-Key` 幂等

**请求体参数**

| 参数      | 必填 | 类型      | 说明             |
| ------- | -- | ------- | -------------- |
| `force` | 否  | boolean | 是否忽略当前已有译文重新翻译 |

**返回结构**

| 字段                     | 类型           | 说明                   |
| ---------------------- | ------------ | -------------------- |
| `data.content_item_id` | string(uuid) | 内容 ID                |
| `data.current_stage`   | string       | 当前阶段，固定为 `translate` |
| `data.run_id`          | string(uuid) | 翻译任务运行 ID            |
| `data.status`          | string       | 任务状态                 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "translation queued",
  "data": {
    "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
    "current_stage": "translate",
    "run_id": "8bc5a941-004f-4107-adf0-bbe5458bf08d",
    "status": "queued"
  },
  "meta": {
    "request_id": "req_translate_001",
    "run_id": "8bc5a941-004f-4107-adf0-bbe5458bf08d"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `PIPELINE_TRANSLATE_FAILED`
- `CONTENT_STATUS_CONFLICT`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 7.7 从指定阶段重试

- **方法**：`POST`
- **路径**：`/api/admin/content-items/{content_item_id}/retry`
- **功能描述**：按阶段重试失败任务。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数       | 必填 | 类型     | 说明                                                                       |
| -------- | -- | ------ | ------------------------------------------------------------------------ |
| `stage`  | 是  | string | `fetch`、`extract`、`transcribe`、`translate`、`research`、`publish`、`notify` |
| `reason` | 否  | string | 管理员重试备注                                                                  |

**返回结构**

| 字段                     | 类型           | 说明     |
| ---------------------- | ------------ | ------ |
| `data.content_item_id` | string(uuid) | 内容 ID  |
| `data.stage`           | string       | 重试起始阶段 |
| `data.run_id`          | string(uuid) | 新运行 ID |
| `data.status`          | string       | 任务状态   |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "retry queued",
  "data": {
    "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
    "stage": "extract",
    "run_id": "run_2d9447fc-7da0-4a43-8af0-ec67aef5f814",
    "status": "queued"
  },
  "meta": {
    "request_id": "req_retry_001",
    "run_id": "run_2d9447fc-7da0-4a43-8af0-ec67aef5f814"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `PIPELINE_STAGE_NOT_RETRYABLE`
- `CONTENT_STATUS_CONFLICT`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 7.8 发布到公开站点

- **方法**：`POST`
- **路径**：`/api/admin/content-items/{content_item_id}/publish/web`
- **功能描述**：将审核通过内容发布到公开站点，并生成 / 更新页面投影。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数                | 必填 | 类型     | 说明               |
| ----------------- | -- | ------ | ---------------- |
| `slug`            | 否  | string | 自定义 slug，不传则自动生成 |
| `seo_title`       | 否  | string | SEO 标题           |
| `seo_description` | 否  | string | SEO 描述           |

**返回结构**

| 字段                       | 类型               | 说明          |
| ------------------------ | ---------------- | ----------- |
| `data.content_item_id`   | string(uuid)     | 内容 ID       |
| `data.publish_record_id` | string(uuid)     | Web 发布记录 ID |
| `data.slug`              | string           | 已生效 slug    |
| `data.url`               | string           | 公开访问地址      |
| `data.published_at`      | string(datetime) | 发布完成时间      |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "web publish succeeded",
  "data": {
    "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
    "publish_record_id": "0f89e1c2-ec16-4be0-9031-1df532f4ef43",
    "status": "published",
    "slug": "the-future-of-ai-design-systems",
    "url": "https://www.example.com/articles/the-future-of-ai-design-systems",
    "published_at": "2026-06-04T12:30:00Z"
  },
  "meta": {
    "request_id": "req_publish_web_001"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `CONTENT_NOT_READY_FOR_PUBLISH`
- `CONTENT_STATUS_CONFLICT`
- `CONTENT_SLUG_CONFLICT`
- `SYSTEM_INTERNAL_ERROR`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

## 8. 工作流监控 API

### 8.1 手工触发巡检

- **方法**：`POST`
- **路径**：`/api/admin/workflow/discover`
- **功能描述**：管理员手工触发一次 Discover 任务。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数           | 必填 | 类型                   | 说明                |
| ------------ | -- | -------------------- | ----------------- |
| `source_ids` | 否  | array\<string(uuid)> | 指定来源范围；为空表示全部启用来源 |
| `notes`      | 否  | string               | 手工任务备注            |

**返回结构**

| 字段                      | 类型           | 说明      |
| ----------------------- | ------------ | ------- |
| `data.discovery_run_id` | string(uuid) | 巡检任务主键  |
| `data.run_id`           | string(uuid) | 追踪运行 ID |
| `data.status`           | string       | 入队状态    |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "discover queued",
  "data": {
    "discovery_run_id": "1b224c09-99f2-4b87-835b-d63a6097e040",
    "run_id": "cc196d2e-6be3-437a-b147-2d0ec710cd31",
    "status": "queued"
  },
  "meta": {
    "request_id": "req_discover_001",
    "run_id": "cc196d2e-6be3-437a-b147-2d0ec710cd31"
  }
}
```

**错误码**

- `WORKFLOW_SOURCE_SCOPE_INVALID`
- `SYSTEM_INTERNAL_ERROR`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 8.2 获取运行列表

- **方法**：`GET`
- **路径**：`/api/admin/workflow/runs`
- **功能描述**：工作流监控总览列表。
- **权限**：管理员
- **幂等性**：天然幂等

**查询参数**

| 参数                | 必填 | 类型               | 说明   |
| ----------------- | -- | ---------------- | ---- |
| `page`            | 否  | integer          | 页码   |
| `page_size`       | 否  | integer          | 每页大小 |
| `status`          | 否  | string           | 运行状态 |
| `stage`           | 否  | string           | 阶段过滤 |
| `content_item_id` | 否  | string(uuid)     | 内容过滤 |
| `date_from`       | 否  | string(datetime) | 开始时间 |
| `date_to`         | 否  | string(datetime) | 结束时间 |

**返回结构**

| 字段                         | 类型            | 说明     |
| -------------------------- | ------------- | ------ |
| `data.items[]`             | array<object> | 运行列表   |
| `data.items[].run_id`      | string(uuid)  | 运行 ID  |
| `data.items[].status`      | string        | 运行状态   |
| `data.items[].stage`       | string        | 当前阶段   |
| `data.items[].duration_ms` | integer/null  | 当前已耗时  |
| `data.items[].error_code`  | string/null   | 最近错误码  |
| `data.summary`             | object        | 当页汇总统计 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "run_id": "cc196d2e-6be3-437a-b147-2d0ec710cd31",
        "discovery_run_id": "1b224c09-99f2-4b87-835b-d63a6097e040",
        "content_item_id": null,
        "status": "success",
        "stage": "notify",
        "duration_ms": 128905,
        "error_code": null,
        "started_at": "2026-06-04T02:00:00Z",
        "ended_at": "2026-06-04T02:02:08Z"
      }
    ],
    "summary": {
      "total_runs": 1,
      "success_runs": 1,
      "failed_runs": 0
    },
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "meta": {
    "request_id": "req_workflow_runs_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`
- `VALIDATION_INVALID_QUERY`

***

### 8.3 获取运行详情

- **方法**：`GET`
- **路径**：`/api/admin/workflow/runs/{run_id}`
- **功能描述**：返回指定 `run_id` 的阶段概览、耗时、错误、关联内容。
- **权限**：管理员
- **幂等性**：天然幂等

**路径参数**

| 参数       | 必填 | 类型           | 说明    |
| -------- | -- | ------------ | ----- |
| `run_id` | 是  | string(uuid) | 运行 ID |

**返回结构**

| 字段                        | 类型            | 说明    |
| ------------------------- | ------------- | ----- |
| `data.run`                | object        | 运行主信息 |
| `data.stage_stats[]`      | array<object> | 各阶段统计 |
| `data.related_contents[]` | array<object> | 关联内容  |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "run": {
      "run_id": "cc196d2e-6be3-437a-b147-2d0ec710cd31",
      "status": "success",
      "triggered_by": "scheduler",
      "started_at": "2026-06-04T02:00:00Z",
      "ended_at": "2026-06-04T02:02:08Z"
    },
    "stage_stats": [
      {
        "stage": "discover",
        "status": "success",
        "duration_ms": 8120,
        "attempt_count": 1
      }
    ],
    "related_contents": [
      {
        "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
        "title_zh": "AI 设计系统的未来",
        "status": "published"
      }
    ]
  },
  "meta": {
    "request_id": "req_workflow_run_detail_001"
  }
}
```

**错误码**

- `WORKFLOW_RUN_NOT_FOUND`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 8.4 获取运行日志时间线

- **方法**：`GET`
- **路径**：`/api/admin/workflow/runs/{run_id}/logs`
- **功能描述**：工作流页时间线 / 日志视图所需数据。
- **权限**：管理员
- **幂等性**：天然幂等

**路径参数**

| 参数       | 必填 | 类型           | 说明    |
| -------- | -- | ------------ | ----- |
| `run_id` | 是  | string(uuid) | 运行 ID |

**查询参数**

| 参数                | 必填 | 类型           | 说明      |
| ----------------- | -- | ------------ | ------- |
| `content_item_id` | 否  | string(uuid) | 只看某条内容  |
| `stage`           | 否  | string       | 只看某阶段   |
| `status`          | 否  | string       | 只看失败/成功 |

**返回结构**

| 字段                        | 类型            | 说明      |
| ------------------------- | ------------- | ------- |
| `data.items[]`            | array<object> | 时间线日志项  |
| `data.items[].stage`      | string        | 阶段      |
| `data.items[].status`     | string        | 阶段状态    |
| `data.items[].error_code` | string/null   | 错误码     |
| `data.items[].context`    | object/null   | 阶段上下文摘要 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "8f6db66e-0675-4b29-a116-037db8a83e26",
        "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc",
        "stage": "translate",
        "status": "success",
        "attempt_no": 1,
        "retryable": false,
        "started_at": "2026-06-04T02:01:01Z",
        "ended_at": "2026-06-04T02:01:19Z",
        "duration_ms": 18000,
        "error_code": null,
        "context": {
          "provider": "deepseek",
          "output_blocks": 18
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_workflow_logs_001"
  }
}
```

**错误码**

- `WORKFLOW_RUN_NOT_FOUND`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

## 9. 邮件汇总 API

### 9.1 获取邮件批次列表

- **方法**：`GET`
- **路径**：`/api/admin/email-digests`
- **功能描述**：查看每日汇总邮件批次与发送结果。
- **权限**：管理员
- **幂等性**：天然幂等

**查询参数**

| 参数           | 必填 | 类型           | 说明   |
| ------------ | -- | ------------ | ---- |
| `status`     | 否  | string       | 批次状态 |
| `batch_date` | 否  | string(date) | 指定日期 |
| `page`       | 否  | integer      | 页码   |
| `page_size`  | 否  | integer      | 分页大小 |

**返回结构**

| 字段                            | 类型            | 说明     |
| ----------------------------- | ------------- | ------ |
| `data.items[]`                | array<object> | 邮件批次列表 |
| `data.items[].id`             | string(uuid)  | 批次 ID  |
| `data.items[].batch_date`     | string(date)  | 汇总日期   |
| `data.items[].status`         | string        | 批次状态   |
| `data.items[].content_count`  | integer       | 内容数    |
| `data.items[].delivery_stats` | object        | 投递统计   |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "d75ec986-fe67-4b17-b2f1-b2c0f6ca0c94",
        "batch_date": "2026-06-04",
        "status": "sent",
        "content_count": 5,
        "delivery_stats": {
          "total": 12458,
          "sent": 12420,
          "failed": 38
        },
        "sent_at": "2026-06-04T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "meta": {
    "request_id": "req_email_batches_001"
  }
}
```

**错误码**

- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`
- `VALIDATION_INVALID_QUERY`

***

### 9.2 手工触发每日汇总发送

- **方法**：`POST`
- **路径**：`/api/admin/email-digests/send`
- **功能描述**：管理员手工触发某一天汇总邮件发送。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数             | 必填 | 类型           | 说明     |
| -------------- | -- | ------------ | ------ |
| `batch_date`   | 是  | string(date) | 汇总日期   |
| `force_resend` | 否  | boolean      | 是否强制重发 |

**返回结构**

| 字段                | 类型           | 说明      |
| ----------------- | ------------ | ------- |
| `data.batch_id`   | string(uuid) | 邮件批次 ID |
| `data.batch_date` | string(date) | 批次日期    |
| `data.status`     | string       | 发送状态    |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "email digest send queued",
  "data": {
    "batch_id": "d75ec986-fe67-4b17-b2f1-b2c0f6ca0c94",
    "batch_date": "2026-06-04",
    "status": "sending"
  },
  "meta": {
    "request_id": "req_email_send_001"
  }
}
```

**错误码**

- `EMAIL_DIGEST_BATCH_ALREADY_SENT`
- `EMAIL_DIGEST_NO_CONTENT`
- `INTEGRATION_EMAIL_SEND_FAILED`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

## 10. 微信发布 API

### 10.1 创建微信公众号草稿

- **方法**：`POST`
- **路径**：`/api/admin/wechat/drafts`
- **功能描述**：从已发布内容或手工输入内容创建微信草稿。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**请求体参数**

| 参数                | 必填   | 类型           | 说明                              |
| ----------------- | ---- | ------------ | ------------------------------- |
| `source_mode`     | 是    | string       | `content_item` 或 `manual_input` |
| `content_item_id` | 条件必填 | string(uuid) | `source_mode=content_item` 时必填  |
| `title`           | 条件必填 | string       | 手工模式标题                          |
| `author`          | 否    | string       | 手工模式作者                          |
| `digest`          | 否    | string       | 手工模式摘要                          |
| `body_html`       | 条件必填 | string       | 手工模式正文 HTML                     |
| `show_cover_pic`  | 否    | boolean      | 是否显示封面                          |

**返回结构**

| 字段                       | 类型               | 说明            |
| ------------------------ | ---------------- | ------------- |
| `data.publish_record_id` | string(uuid)     | 发布记录 ID       |
| `data.wechat_draft_id`   | string           | 微信草稿 ID       |
| `data.status`            | string           | 创建状态          |
| `data.created_at`        | string(datetime) | 记录创建时间        |
| `data.error_code`        | string/null      | 平台无关错误码；成功时为空 |
| `data.request_snapshot`  | object           | 请求摘要          |
| `data.response_snapshot` | object           | 微信返回摘要        |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "wechat draft created",
  "data": {
    "publish_record_id": "c9f7fdc8-57d1-4a66-bf63-77c299eff934",
    "wechat_draft_id": "1234567890",
    "status": "success",
    "created_at": "2026-06-04T13:10:00Z",
    "error_code": null,
    "request_snapshot": {
      "source_mode": "content_item",
      "content_item_id": "c1c78b6e-8d3b-4ad2-b6c7-2ec9e5f20abc"
    },
    "response_snapshot": {
      "errcode": 0,
      "errmsg": "ok"
    }
  },
  "meta": {
    "request_id": "req_wechat_draft_001"
  }
}
```

**错误码**

- `CONTENT_NOT_FOUND`
- `CONTENT_NOT_PUBLISHED`
- `VALIDATION_REQUIRED_FIELD_MISSING`
- `INTEGRATION_WECHAT_DRAFT_FAILED`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

***

### 10.2 重试微信草稿创建

- **方法**：`POST`
- **路径**：`/api/admin/wechat/drafts/{publish_record_id}/retry`
- **功能描述**：对失败的微信草稿发布记录进行重试。
- **权限**：管理员
- **幂等性**：需要 `Idempotency-Key`

**路径参数**

| 参数                  | 必填 | 类型           | 说明      |
| ------------------- | -- | ------------ | ------- |
| `publish_record_id` | 是  | string(uuid) | 发布记录 ID |

**返回结构**

| 字段                       | 类型               | 说明          |
| ------------------------ | ---------------- | ----------- |
| `data.publish_record_id` | string(uuid)     | 发布记录 ID     |
| `data.status`            | string           | 重试后的任务状态    |
| `data.retry_count`       | integer          | 累计重试次数      |
| `data.updated_at`        | string(datetime) | 最近一次重试时间    |
| `data.error_code`        | string/null      | 当前错误码；成功时为空 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "wechat draft retry queued",
  "data": {
    "publish_record_id": "c9f7fdc8-57d1-4a66-bf63-77c299eff934",
    "status": "queued",
    "retry_count": 1,
    "updated_at": "2026-06-04T13:20:00Z",
    "error_code": null
  },
  "meta": {
    "request_id": "req_wechat_retry_001"
  }
}
```

**错误码**

- `PUBLISH_RECORD_NOT_FOUND`
- `WECHAT_DRAFT_NOT_RETRYABLE`
- `INTEGRATION_WECHAT_DRAFT_FAILED`
- `AUTH_UNAUTHORIZED`
- `AUTH_FORBIDDEN`

## 11. 第三方回调接口

### 11.1 Resend Webhook

- **方法**：`POST`
- **路径**：`/api/integrations/resend/webhook`
- **功能描述**：接收 Resend 的投递、退信、打开等状态回调，更新 `tb_email_delivery` 与 `tb_subscriber`。
- **权限**：基于服务商签名校验
- **幂等性**：以 `provider_message_id + event_type + occurred_at` 幂等

**请求体参数（示例）**

| 参数                | 必填 | 类型               | 说明       |
| ----------------- | -- | ---------------- | -------- |
| `type`            | 是  | string           | 事件类型     |
| `data.email_id`   | 是  | string           | 服务商消息 ID |
| `data.to`         | 是  | string           | 收件邮箱     |
| `data.created_at` | 是  | string(datetime) | 事件时间     |

**返回结构**

| 字段               | 类型      | 说明           |
| ---------------- | ------- | ------------ |
| `data.processed` | boolean | 是否成功接收并处理该回调 |

**返回示例**

```json
{
  "success": true,
  "code": "OK",
  "message": "webhook accepted",
  "data": {
    "processed": true
  },
  "meta": {
    "request_id": "req_resend_webhook_001"
  }
}
```

**错误码**

- `INTEGRATION_SIGNATURE_INVALID`
- `EMAIL_DELIVERY_NOT_FOUND`
- `SYSTEM_INTERNAL_ERROR`

## 12. 统一错误码表

| 错误码                                  | HTTP 状态     | 说明            |
| ------------------------------------ | ----------- | ------------- |
| `OK`                                 | 200/201/202 | 成功            |
| `AUTH_UNAUTHORIZED`                  | 401         | 未登录或认证失败      |
| `AUTH_FORBIDDEN`                     | 403         | 无后台权限         |
| `AUTH_ACCOUNT_DISABLED`              | 403         | 账号已禁用         |
| `VALIDATION_INVALID_QUERY`           | 400         | 查询参数非法        |
| `VALIDATION_INVALID_URL`             | 400         | URL 非法        |
| `VALIDATION_INVALID_EMAIL`           | 400         | 邮箱非法          |
| `VALIDATION_REQUIRED_FIELD_MISSING`  | 400         | 必填字段缺失        |
| `VALIDATION_INVALID_BODY`            | 422         | 请求体语义不合法      |
| `CONTENT_NOT_FOUND`                  | 404         | 内容不存在         |
| `CONTENT_NOT_PUBLISHED`              | 404         | 内容未发布         |
| `CONTENT_ALREADY_EXISTS`             | 409         | 导入内容已存在       |
| `CONTENT_NOT_READY_FOR_PUBLISH`      | 422         | 内容尚未满足发布条件    |
| `CONTENT_STATUS_CONFLICT`            | 409         | 当前状态不允许操作     |
| `CONTENT_SLUG_CONFLICT`              | 409         | slug 冲突       |
| `SUBSCRIBER_NOT_FOUND`               | 404         | 订阅者不存在        |
| `SUBSCRIPTION_ALREADY_ACTIVE`        | 409         | 已处于订阅状态       |
| `SUBSCRIPTION_ALREADY_UNSUBSCRIBED`  | 409         | 已退订           |
| `SUBSCRIPTION_TOKEN_INVALID`         | 404         | 退订 token 无效   |
| `SUBSCRIPTION_STATUS_CONFLICT`       | 409         | 订阅状态冲突        |
| `SOURCE_NOT_FOUND`                   | 404         | 来源不存在         |
| `WORKFLOW_RUN_NOT_FOUND`             | 404         | 运行记录不存在       |
| `WORKFLOW_SOURCE_SCOPE_INVALID`      | 400         | 巡检来源范围非法      |
| `PIPELINE_STAGE_NOT_RETRYABLE`       | 409         | 阶段不可重试        |
| `PIPELINE_FETCH_FAILED`              | 502         | 抓取失败          |
| `PIPELINE_EXTRACT_FAILED`            | 422         | 抽取失败          |
| `PIPELINE_TRANSLATE_FAILED`          | 502         | 翻译失败          |
| `PIPELINE_RESEARCH_FAILED`           | 502         | 研究报告失败        |
| `EMAIL_DIGEST_BATCH_ALREADY_SENT`    | 409         | 批次已发送         |
| `EMAIL_DIGEST_NO_CONTENT`            | 422         | 批次无内容可发送      |
| `EMAIL_DELIVERY_NOT_FOUND`           | 404         | 邮件投递记录不存在     |
| `INTEGRATION_EMAIL_SEND_FAILED`      | 502         | 邮件发送失败        |
| `INTEGRATION_WECHAT_DRAFT_FAILED`    | 502         | 微信草稿创建失败      |
| `INTEGRATION_COS_UPLOAD_FAILED`      | 502         | COS 上传失败      |
| `INTEGRATION_SIGNATURE_INVALID`      | 401         | 回调签名无效        |
| `PUBLISH_RECORD_NOT_FOUND`           | 404         | 发布记录不存在       |
| `WECHAT_DRAFT_NOT_RETRYABLE`         | 409         | 微信草稿记录不可重试    |
| `SYSTEM_CONFIG_MISSING`              | 500         | 关键配置缺失        |
| `SYSTEM_INTERNAL_ERROR`              | 500         | 系统内部错误        |

## 13. 权限校验规则

| 接口范围          | 权限规则                       |
| ------------- | -------------------------- |
| 公开页面 / 公开 API | 无需登录                       |
| 后台页面          | 必须管理员登录                    |
| 后台读 API       | 必须管理员 Session 有效           |
| 后台写 API       | 必须管理员 Session 有效 + CSRF 校验 |
| 第三方回调         | 必须校验签名或来源令牌                |

## 14. 覆盖性校验结果

本 API 设计已覆盖以下全部业务功能：

- 公开站点：首页、列表页、Archive、详情页、静态页、退订页
- 公开交互：订阅、退订、列表筛选、双语详情数据
- 后台登录：管理员登录、登出、当前用户
- 仪表盘：指标、近期动态、系统状态
- 来源治理：来源列表、启停与调度配置
- 内容管理：列表、详情、URL 导入、纯手工录入、编辑、翻译、重试、发布
- 工作流监控：手工巡检、运行列表、运行详情、时间线 / 日志视图
- 邮件：订阅状态、每日汇总批次、手工发送、Webhook 回写
- 微信：草稿创建、失败重试
- 统一治理：幂等性、错误码、统一响应结构、认证与权限
- 订阅与通知能力已按确认后的每日汇总邮件策略定稿
