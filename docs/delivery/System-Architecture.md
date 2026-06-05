# TechBrief 系统架构图

更新时间：2026-06-03

## 1. 文档目标

本文基于当前已确认的 PRD 与技术方案，输出一份可执行的系统架构图文档。文档采用自顶向下的方式描述：

- 产品边界与访问入口；
- 系统内部功能模块划分；
- 核心数据与基础设施依赖；
- 自动内容处理主链路时序；
- 核心业务流程图。

当前架构以单人维护、MVP 快速落地为前提，遵循“简单、可运行、可追溯、可扩展”的原则，不引入复杂权限系统和过度拆分的微服务架构。

## 2. 顶层架构

```mermaid
graph TB
    Reader["读者"]
    Operator["运营者 / 管理员"]

    PublicDomain["www.example.com<br/>公开站点"]
    AdminDomain["admin.example.com<br/>管理后台"]

    subgraph App["TechBrief Django + Wagtail 单体应用"]
        Web["Web 层<br/>首页 / 列表 / 详情 / 静态页 / 订阅弹窗"]
        AdminConsole["Admin Console<br/>仪表盘 / 内容管理 / 订阅管理 / 工作流监控 / 微信草稿工具"]
        Pipeline["Content Pipeline<br/>Discover / Fetch / Extract / Translate / Research / Review / Publish / Notify"]
        Publishers["Publishers<br/>Web Publish / Email Digest / WeChat Draft"]
        Analytics["Analytics Adapter<br/>GA4 事件注入"]
    end

    subgraph Infra["基础设施"]
        Postgres["PostgreSQL<br/>业务主库"]
        Redis["Redis<br/>Celery Broker / Cache"]
        COS["腾讯云 COS<br/>原始大对象存储"]
    end

    subgraph External["外部集成"]
        Sources["内容来源<br/>OpenAI / Anthropic / 视频平台"]
        LLM["LLM Provider<br/>翻译 / 研究"]
        Resend["Resend<br/>邮件发送"]
        WeChat["微信草稿 API"]
        GA4["Google Analytics 4"]
    end

    Reader --> PublicDomain --> Web
    Operator --> AdminDomain --> AdminConsole

    Web --> Analytics --> GA4
    Web --> Postgres
    AdminConsole --> Postgres
    AdminConsole --> Publishers

    Pipeline --> Postgres
    Pipeline --> Redis
    Pipeline --> COS
    Pipeline --> Sources
    Pipeline --> LLM
    Publishers --> Resend
    Publishers --> WeChat
    Publishers --> Postgres
```

## 3. 模块分层

```mermaid
graph TD
    subgraph Presentation["表现层"]
        PublicWeb["公开站点<br/>Wagtail Page + Templates"]
        BackOffice["后台管理<br/>Wagtail Admin + Staff Views"]
    end

    subgraph Application["应用层"]
        ContentService["内容服务<br/>内容查询 / 发布快照 / 手工录入"]
        SubscriptionService["订阅服务<br/>订阅 / 退订 / Digest 生成"]
        WorkflowService["工作流服务<br/>任务编排 / 重试 / RunLog"]
        ChannelService["渠道服务<br/>Web / Email / WeChat"]
        AuthBootstrap["认证初始化<br/>初始管理员自动注入"]
    end

    subgraph Domain["领域对象"]
        ContentItem["ContentItem"]
        Subscriber["Subscriber"]
        PublishRecord["PublishRecord"]
        RunLog["RunLog"]
        ArticlePage["ArticlePage / VideoPage"]
    end

    subgraph Integration["集成层"]
        SourceAdapters["Source Adapters<br/>RSS / HTML List / Video Channel"]
        Extractors["Extractors<br/>Trafilatura / readability-lxml / Jina fallback"]
        Media["Media Processors<br/>yt-dlp / ffmpeg / ASR API Client"]
        AI["AI Adapters<br/>ASR / Translation / Research"]
        Mail["Email Adapter<br/>Resend"]
        WechatAdapter["WeChat Adapter"]
        GAAdapter["GA4 Adapter"]
    end

    subgraph Storage["存储层"]
        DB["PostgreSQL"]
        ObjectStore["腾讯云 COS"]
        Broker["Redis"]
    end

    PublicWeb --> ContentService
    PublicWeb --> SubscriptionService
    PublicWeb --> GAAdapter

    BackOffice --> ContentService
    BackOffice --> WorkflowService
    BackOffice --> ChannelService
    BackOffice --> AuthBootstrap

    ContentService --> ContentItem
    ContentService --> ArticlePage
    SubscriptionService --> Subscriber
    WorkflowService --> RunLog
    ChannelService --> PublishRecord

    WorkflowService --> SourceAdapters
    WorkflowService --> Extractors
    WorkflowService --> Media
    WorkflowService --> AI
    ChannelService --> Mail
    ChannelService --> WechatAdapter

    ContentItem --> DB
    Subscriber --> DB
    PublishRecord --> DB
    RunLog --> DB
    ArticlePage --> DB

    SourceAdapters --> Broker
    Extractors --> ObjectStore
    Media --> ObjectStore
    AI --> DB
    Mail --> DB
    WechatAdapter --> DB
```

## 4. 存储架构

```mermaid
graph LR
    subgraph PostgreSQL["PostgreSQL（业务主库）"]
        PG1["ContentItem<br/>结构化原文 / 中文内容 / 状态 / 去重"]
        PG2["Subscriber<br/>订阅状态"]
        PG3["PublishRecord<br/>Web / Email / WeChat 发布记录"]
        PG4["RunLog<br/>阶段日志 / 错误 / 耗时"]
        PG5["Wagtail Pages<br/>ArticlePage / VideoPage / StaticPage"]
    end

    subgraph COS["腾讯云 COS（对象存储）"]
        COS1["raw_html"]
        COS2["原始抓取响应"]
        COS3["字幕文件 / 转录分段 JSON"]
        COS4["音频文件"]
        COS5["封面原图 / 原始图片"]
    end

    subgraph Redis["Redis"]
        R1["Celery Broker"]
        R2["任务队列 / 重试 / 限流辅助"]
    end

    PG1 --> COS1
    PG1 --> COS2
    PG1 --> COS3
    PG1 --> COS4
    PG1 --> COS5
```

## 5. 域名与访问控制

```mermaid
graph TB
    Internet["公网访问"]
    Nginx["反向代理 / HTTPS 入口"]
    PublicHost["www.example.com"]
    AdminHost["admin.example.com"]
    DjangoApp["Django + Wagtail App"]
    PublicPages["公开站点页面"]
    AdminLogin["管理员登录"]
    AdminViews["后台管理页面"]
    Bootstrap["启动时管理员注入"]
    Config["配置文件 / 环境变量<br/>INITIAL_ADMIN_USERNAME / PASSWORD / EMAIL"]
    DB["PostgreSQL"]

    Internet --> Nginx
    Nginx --> PublicHost --> DjangoApp --> PublicPages
    Nginx --> AdminHost --> DjangoApp --> AdminLogin --> AdminViews
    Config --> Bootstrap --> DB
    AdminLogin --> DB
```

## 6. 自动内容处理主链路时序图

```mermaid
sequenceDiagram
    autonumber
    participant Beat as django-celery-beat
    participant Worker as Celery Worker
    participant Source as Source Adapter
    participant Site as 来源站点
    participant DB as PostgreSQL
    participant COS as 腾讯云 COS
    participant Extract as Extractor
    participant Media as 媒体处理器
    participant LLM as LLM Provider
    participant Admin as 管理后台
    participant Mail as Resend

    Beat->>Worker: 触发每日 discover 任务
    Worker->>Source: 拉取 RSS / 列表页 / sitemap
    Source->>Site: 请求官方发现源
    Site-->>Source: 返回 URL / lastmod / metadata
    Source->>DB: 按 dedupe_key 做新增/更新入队

    loop 对每条待处理内容
        Worker->>Site: 请求详情页 / 视频元信息
        Site-->>Worker: HTML / metadata / subtitle info
        Worker->>COS: 保存 raw_html / 原始响应
        Worker->>Extract: 结构化抽取正文与 metadata
        Extract-->>Worker: content_ast / content_md / metadata_json
        Worker->>DB: 保存结构化原文

        alt 视频无字幕
            Worker->>Media: 提取音频并转录
            Media->>COS: 保存音频 / transcript artifacts
            Media-->>Worker: transcript_text / segments_json
        end

        Worker->>LLM: 分块翻译 / 研究报告生成
        LLM-->>Worker: zh_ast / zh_md / research_report_md
        Worker->>DB: 写入中文内容并置为 review_pending
        Worker->>DB: 写入 RunLog
    end

    Admin->>DB: 查看 review_pending 内容
    Admin->>DB: 手动发布到 Web
    DB->>DB: 同步发布快照到 ArticlePage / VideoPage
    Worker->>Mail: 生成并发送每日 Digest
    Mail-->>Worker: 投递结果
    Worker->>DB: 回写 PublishRecord / RunLog
```

## 7. 自动内容处理流程图

```mermaid
flowchart TD
    Start([定时任务触发])
    Discover[发现内容<br/>RSS / 列表页 / sitemap]
    Dedupe{是否已存在且未变化?}
    Fetch[抓取详情页 / 元信息]
    SaveRaw[保存 raw_html / 原始响应到 COS]
    Extract[抽取正文 / 元信息]
    VideoCheck{是否为无字幕视频?}
    Transcribe[提取音频并转录]
    Translate[分块翻译]
    Research[生成研究报告]
    Validate[结构校验]
    Review[进入后台待审核]
    Publish[管理员手动发布]
    Snapshot[生成站内发布快照]
    Notify[发送每日 Digest]
    End([结束])
    Skip([跳过])
    Failed[记录失败阶段与错误]

    Start --> Discover --> Dedupe
    Dedupe -- 是 --> Skip --> End
    Dedupe -- 否 --> Fetch --> SaveRaw --> Extract
    Extract --> VideoCheck
    VideoCheck -- 是 --> Transcribe --> Translate
    VideoCheck -- 否 --> Translate
    Translate --> Research --> Validate
    Validate -- 通过 --> Review --> Publish --> Snapshot --> Notify --> End
    Validate -- 失败 --> Failed --> End
    Fetch -.失败.-> Failed
    Extract -.失败.-> Failed
    Transcribe -.失败.-> Failed
    Translate -.失败.-> Failed
```

## 8. 后台审核与手动发布流程图

```mermaid
flowchart TD
    A([管理员登录 admin.example.com])
    B[查看 Dashboard / Content Management]
    C{内容来源}
    D[选择自动采集内容]
    E[手动录入 URL]
    F[纯手工录入原文 / 译文 / 来源]
    G[预览原文 / 译文 / 渲染结果]
    H{是否发布到 Web?}
    I[发布到公开站点]
    J{是否生成微信草稿?}
    K[渲染微信 HTML]
    L[上传封面和正文图片]
    M[调用草稿接口]
    N[记录 wechat_draft_id]
    O([结束])

    A --> B --> C
    C --> D --> G
    C --> E --> G
    C --> F --> G
    G --> H
    H -- 否 --> O
    H -- 是 --> I --> J
    J -- 否 --> O
    J -- 是 --> K --> L --> M --> N --> O
```

## 9. 关键架构决策

- **单体优先**：采用 Django + Wagtail 单体架构，减少单人项目的部署与维护成本。
- **模块内聚**：公开站点、后台管理、内容流水线、渠道发布在同一应用内分模块组织，而不是拆成多个服务。
- **数据库与对象存储分层**：结构化业务数据进入 PostgreSQL，raw HTML、字幕、音频、图片进入腾讯云 COS。
- **异步任务统一编排**：内容发现、抓取、翻译、转录、邮件发送统一交给 Celery + `django-celery-beat`。
- **人工发布把关**：自动处理只负责生成待审核内容，最终 Web 发布与微信草稿生成都需要管理员确认。
- **权限保持简单**：后台只采用管理员登录，不设计复杂角色系统。

## 10. 建议的后续落地图谱

- 先落库核心模型：`ContentItem`、`Subscriber`、`PublishRecord`、`RunLog`
- 再实现基础页面：首页、列表页、详情页、后台登录
- 然后接通自动采集主链路：discover -> fetch -> extract -> translate -> review
- 最后补齐运营能力：digest 邮件、微信草稿工具、GA4 埋点、后台工作流监控
