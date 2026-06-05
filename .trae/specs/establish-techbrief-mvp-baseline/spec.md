# TechBrief MVP 交付基线 Spec

## Why
当前仓库已完成 PRD、技术方案、架构、API、数据库、验收清单与前端原型素材沉淀，但尚未进入正式工程实现。为避免团队在需求理解、范围边界、验收口径和前端还原标准上出现偏差，需要先建立统一的实施基线，再进入开发与验证。

## What Changes
- 建立“全文档归集与学习完成后才能启动实现”的交付前置要求
- 固化 PRD、技术方案、架构、数据库、API、验收清单之间的统一优先级与冲突裁决规则
- 将 MVP 范围拆解为公开站点、后台管理、内容流水线、邮件订阅、微信草稿五大能力域
- 将前端实现约束提升为强制要求：严格遵循 `stitch_ai_insight_bridge` 中的设计系统、HTML 原型和后台截图
- 明确当前信息缺口及处理方式：无法从仓库文档闭合的事项需补充外部资料或由产品确认

## Impact
- Affected specs: 文档归集基线、需求对齐基线、前端保真基线、MVP 交付基线
- Affected code: `README.md`、`TechBrief-PRD.md`、`docs/delivery/*`、`stitch_ai_insight_bridge/*`、未来 `web` / `admin_console` / `content_pipeline` / `publishers` / `integrations` / `observability`

## Task 1-2 Audit Status
### Task 1: 文档基线确认
- 当前仓库已经具备可核对的文档归集证据：`README.md` 提供正式文档导航，`docs/delivery/Delivery-Guide.md` 列出目标交付物，`docs/delivery/Database-Design.md` 与 `docs/delivery/API-Design.md` 均声明以 PRD、技术方案和 `stitch_ai_insight_bridge` 为输入
- 当前仓库已经具备可核对的优先级与冲突裁决规则：以 `TechBrief-PRD.md -> docs/delivery/Technical-Solution-Report.md -> docs/delivery/Database-Design.md -> docs/delivery/API-Design.md -> docs/delivery/Acceptance-Checklist.md -> stitch_ai_insight_bridge/*` 为正式裁决链，`README.md` 仅作为导航入口，不作为冲突裁决源
- `SubTask 1.3` 所要求的外部补充调研已经完成并形成事实依据：Google 官方文档已确认 GA4 需要 property、web data stream 与 Google tag，且 `page_view` 默认自动采集；Resend 官方文档已确认发送前需完成域名校验、DNS 记录配置与 API Key 创建，且校验通过后可从该域任意地址发信；腾讯云 COS 官方文档已确认 bucket、region、`SecretId`、`SecretKey` 与 `https` 协议配置要求；微信服务号官方文档已确认 `/cgi-bin/draft/add`、`/cgi-bin/draft/batchget` 等草稿箱接口存在，且 `access_token` 有效期 7200 秒并应由中控统一刷新；yt-dlp 官方 `supportedsites.md` 已证明技术上可覆盖大量公开视频站点，但是否可用仍需逐站点实测；MiMo 官方文档已确认 `mimo-v2.5` 支持公网音频 URL 与 Base64 两种输入，其中 URL 方式单文件上限 100 MB、Base64 方式上限 50 MB
- Task 1 仍不能判定为完全完成，但阻塞原因已从“缺少外部证据”收敛为“仍有内部决策未拍板”
- 当前剩余阻塞缺口全部属于内部确认项：PRD 仍为“草案（待评审）”；公开域名、后台域名、DNS、HTTPS、GA4、COS、Resend、微信等资源与凭据由谁提供/谁持有未确认；“更多公开视频平台”的首批白名单未锁定；视频时长上限与“无字幕视频是否全部转录或按优先级转录”未锁定；研究报告是否允许站内公开未锁定；初始管理员账号是否允许后续在后台修改用户名/密码未锁定

### Task 2: MVP 能力域与范围边界
- 当前仓库已经具备可核对的能力域拆分证据：公开站点、后台管理、内容流水线、邮件订阅、微信草稿五大能力域已在 PRD、交付说明和本 spec 中反复对齐
- 当前仓库已经具备可核对的范围边界证据：P0 页面、接口分区、核心数据对象、状态链路、外部集成、非目标与降级策略已分别落在 PRD、技术方案、系统架构、数据库设计、API 设计、交付说明与验收清单中
- Task 2 可按“文档基线已锁定”判定完成，但工程启动仍需等待 Task 1 中未闭合缺口被补齐或被明确豁免

## ADDED Requirements
### Requirement: 全文档先行归集与统一认知
系统实施 SHALL 在任何编码工作开始前完成项目内全文档归集、阅读和交叉核对，并形成一份覆盖核心目标、功能边界、业务规则、验收标准和信息缺口的统一认知基线。

#### Scenario: 实施前置检查通过
- **WHEN** 团队准备开始某项实现任务
- **THEN** 必须先完成对 `README.md`、PRD、技术方案、系统架构、数据库设计、API 设计、交付说明、验收清单以及 `stitch_ai_insight_bridge` 全部资料的阅读与归集
- **AND** 必须明确文档优先级为 PRD、技术方案、数据库设计、API 设计、验收清单、原型素材
- **AND** 未完成上述归集前不得进入编码阶段

#### Scenario: 发现信息缺口
- **WHEN** 文档之间存在冲突、缺页、缺少交互状态定义、外部集成边界不明或实现条件缺失
- **THEN** 团队必须先记录缺口
- **AND** 对可由外部公开资料补足的内容，主动使用联网搜索或 MCP 获取事实依据
- **AND** 对无法由外部资料闭合的产品决策，保留为待确认项并阻止相关实现进入开发

### Requirement: 需求拆解必须覆盖全部 MVP 能力域
系统规划 SHALL 将现有文档中的需求拆解为公开站点、后台管理、内容发现与处理、邮件订阅与通知、微信公众号手动发布五个能力域，并为每个能力域建立明确的输入、输出、状态和验收口径。

#### Scenario: 形成功能清单
- **WHEN** 团队基于文档输出实施计划
- **THEN** 必须至少覆盖首页、列表页、详情页、Archive、About、Privacy、Terms、订阅弹窗、管理员登录、仪表盘、来源管理、内容管理、订阅管理、工作流监控、手动录入、微信草稿发布
- **AND** 必须覆盖 `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending -> publish -> notify` 全链路
- **AND** 必须覆盖 `article`、`video`、`manual` 三类内容对象

#### Scenario: 形成功能边界
- **WHEN** 团队定义 MVP 范围
- **THEN** 必须将评论、点赞、用户投稿、复杂 RBAC、多语言内容生产、全自动公众号发布等能力排除在 MVP 外
- **AND** 必须将每日汇总邮件定义为默认通知策略
- **AND** 必须将微信公众号能力限定为后台手动工具，不得阻断主站发布

### Requirement: 前端实现必须高保真还原 stitch_ai_insight_bridge
前端实现 SHALL 严格以 `stitch_ai_insight_bridge` 中的设计规范、HTML 原型和后台截图为准，保证视觉语言、布局结构、交互流程、响应式规则和主题模式与原型效果高度一致。

#### Scenario: 公开站点页面实现
- **WHEN** 团队实现首页、详情页、订阅弹窗、后台页面及其衍生页面
- **THEN** 每个已交付页面和状态都必须能追溯到 `liquid_narrative/DESIGN.md`、公开 HTML 原型、后台截图或一份明确补齐的缺失规格
- **AND** 首页、详情页、订阅弹窗必须保持与现有 HTML 原型一致的布局骨架、视觉层级、关键交互和信息分区，不得因实现便利自行改版
- **AND** 后台仪表盘、订阅者、内容管理、工作流监控、手动发布页面必须以截图为强制参照，锁定信息架构、表格/卡片密度、状态标签、筛选区和主操作位
- **AND** 必须复用 Liquid Glass 设计语言，包括玻璃拟态表面、模糊背景、渐变强调、圆角体系、排版和间距节奏
- **AND** 必须支持 Desktop / Tablet / Mobile 响应式布局
- **AND** 必须支持 Light / Dark mode
- **AND** 详情页必须支持中文单栏与中英双栏阅读模式、阅读进度条和悬浮订阅入口

#### Scenario: 原型覆盖不完整
- **WHEN** 某页面或状态在 `stitch_ai_insight_bridge` 中缺少可运行原型
- **THEN** 团队必须以 PRD、技术方案和已有设计系统为约束补齐缺失定义
- **AND** 不得擅自改变已存在原型中的布局逻辑、视觉风格和核心交互流程
- **AND** 补齐内容至少包括文章列表页、Archive、About、Privacy、Terms、退订确认/成功页
- **AND** 必须补齐订阅邮箱无效、提交中、失败、重复订阅、成功后的返回路径
- **AND** 必须补齐公开站点的空态、无结果态、404/内容不存在态，以及详情页缺少译文、缺少原文、缺少封面图时的降级态
- **AND** 必须补齐后台页面的加载态、空数据态、错误态、删除/发布确认态、操作成功/失败反馈态
- **AND** 上述缺失页面和状态在形成书面规格与验收口径前不得视为 Task 3 完成

#### Scenario: Task 3 完成验收
- **WHEN** 团队宣称“锁定前端保真实现基线”已完成
- **THEN** 必须交付一份页面/组件/状态清单，并为每一项标注来源素材、缺口补齐依据和适用端
- **AND** 必须交付一份前端验收矩阵，覆盖布局层级、文案槽位、视觉 token、断点规则、主题切换、交互触发、反馈状态和降级策略
- **AND** 首页、详情页、订阅弹窗、五个后台页面必须分别具备可核对的高保真验收条目，而非仅有笼统“参考原型”描述
- **AND** 未形成上述映射和验收明细前，不得进入正式前端开发或标记 Task 3 完成

### Task 3 页面 / 组件 / 状态映射基线
| 类型 | 交付对象 | 来源素材 | 关键组件 | 必备状态 | 适用端 | 缺口补齐依据 |
| --- | --- | --- | --- | --- | --- | --- |
| Public Page | 首页 | `stitch_ai_insight_bridge/homepage_public/code.html`、`screen.png`、`liquid_narrative/DESIGN.md` | 顶部导航、Hero、内容卡片流、来源标签、订阅入口、页脚 | 默认、加载、空态、无结果态 | Desktop / Tablet / Mobile | `TechBrief-PRD.md` 5.1、6.1、`docs/delivery/Acceptance-Checklist.md` 2.5 |
| Public Page | 详情页 | `stitch_ai_insight_bridge/article_detail_public/code.html`、`screen.png`、`liquid_narrative/DESIGN.md` | 标题区、元信息、中文正文、双语切换、阅读进度条、悬浮订阅入口、免责声明 | 默认、加载、内容不存在、缺少译文、缺少原文、缺少封面 | Desktop / Tablet / Mobile | `TechBrief-PRD.md` 5.1、6.1、8.5、`docs/delivery/Acceptance-Checklist.md` 2.5 |
| Public Page | 订阅弹窗 | `stitch_ai_insight_bridge/subscription_modal_public/code.html`、`screen.png`、`liquid_narrative/DESIGN.md` | 标题文案、邮箱输入、提交按钮、关闭按钮、成功反馈区 | 默认、邮箱无效、提交中、失败、重复订阅、成功 | Desktop / Tablet / Mobile | `TechBrief-PRD.md` 5.1、8.6、`docs/delivery/Acceptance-Checklist.md` 2.6 |
| Public Page | 列表页 | `liquid_narrative/DESIGN.md` + 首页 / 详情页原型 | 导航、筛选条、列表卡片、分页或加载更多、订阅入口、页脚 | 默认、加载、空态、无结果态 | Desktop / Tablet / Mobile | `TechBrief-PRD.md` 5.1、6.1、8.5、`README.md` MVP 范围 |
| Public Page | Archive / About / Privacy / Terms | `liquid_narrative/DESIGN.md` + 首页 / 详情页原型 | 静态内容容器、导航、页脚、运营文案双语槽位 | 默认、加载、内容不存在 | Desktop / Tablet / Mobile | `TechBrief-PRD.md` 5.1、8.5、`docs/delivery/Acceptance-Checklist.md` 2.5 |
| Public Page | 退订确认页 / 退订成功页 | `liquid_narrative/DESIGN.md` + 订阅弹窗原型 | 结果说明、主按钮、返回首页入口、邮件状态提示 | 默认、处理中、成功、失败、重复操作 | Desktop / Tablet / Mobile | `TechBrief-PRD.md` 8.6、`docs/delivery/Acceptance-Checklist.md` 2.6 |
| Admin Page | 仪表盘 | `stitch_ai_insight_bridge/admin_dashboard_management/screen.png`、`liquid_narrative/DESIGN.md` | KPI 卡片、趋势区、最近动态、系统状态、主操作位 | 默认、加载、空数据、错误 | Desktop 优先，Tablet 次级 | `TechBrief-PRD.md` 5.2、8.7、`docs/delivery/Acceptance-Checklist.md` 2.7 |
| Admin Page | 订阅者管理 | `stitch_ai_insight_bridge/admin_subscribers_management/screen.png`、`liquid_narrative/DESIGN.md` | 筛选条、表格、状态标签、搜索、分页、批量或单项操作位 | 默认、加载、空数据、错误、删除或退订确认、成功 / 失败反馈 | Desktop 优先，Tablet 次级 | `TechBrief-PRD.md` 5.2、8.7、`docs/delivery/Acceptance-Checklist.md` 2.7 |
| Admin Page | 内容管理 | `stitch_ai_insight_bridge/admin_content_management_management/screen.png`、`liquid_narrative/DESIGN.md` | 筛选条、内容表格、状态标签、预览入口、发布 / 重试 / 手动录入操作位 | 默认、加载、空数据、错误、发布确认、重试确认、成功 / 失败反馈 | Desktop 优先，Tablet 次级 | `TechBrief-PRD.md` 5.2、8.7、`docs/delivery/Acceptance-Checklist.md` 2.7 |
| Admin Page | 工作流监控 | `stitch_ai_insight_bridge/admin_workflow_monitor_management/screen.png`、`liquid_narrative/DESIGN.md` | 阶段状态卡、时间线、日志视图、重跑入口、筛选器 | 默认、加载、空数据、错误、重跑确认、成功 / 失败反馈 | Desktop 优先，Tablet 次级 | `TechBrief-PRD.md` 5.2、7.1、8.7、`docs/delivery/Acceptance-Checklist.md` 2.7 |
| Admin Page | 手动发布 / 微信草稿 | `stitch_ai_insight_bridge/admin_manual_publish_management/screen.png`、`liquid_narrative/DESIGN.md` | 内容选择器、手工输入表单、封面 / 摘要 / 作者复用区、草稿结果区 | 默认、加载、空数据、错误、提交中、发布确认、成功 / 失败反馈 | Desktop 优先，Tablet 次级 | `TechBrief-PRD.md` 5.2、8.8、`docs/delivery/Acceptance-Checklist.md` 2.8 |

### Task 3 缺失页面显式规格
#### Public Page: 列表页
- 路由职责：承接首页卡片、导航和筛选跳转后的标准内容浏览入口，展示文章 / 视频混合流，并支持来源、类型、时间三个维度的筛选与清空
- 布局骨架：沿用首页导航、玻璃容器和页脚；主内容区由页面标题、结果统计、筛选条、卡片列表、分页或“加载更多”组成；移动端优先折叠筛选区
- 内容槽位：每张卡片必须展示标题、内容类型、来源名、发布时间、摘要或导语、封面图或占位图，以及跳转详情页的完整点击热区
- 交互约束：筛选条件变化后保留当前可见条件标签与结果数；清空筛选返回默认列表态；无结果时保留筛选条件回显与一键清空入口
- 验收口径：视觉 token 复用首页；空态、无结果态、404/内容不存在态均必须保留导航、返回首页路径和订阅入口

#### Public Page: Archive
- 路由职责：提供按月份或时间分组的历史内容浏览入口，强调时间维度导航，不替代标准筛选列表页
- 布局骨架：沿用公开站点导航和页脚；主内容区由归档标题、时间分组导航、按时间倒序排列的卡片列表组成
- 内容槽位：每个归档分组必须展示时间标签、该时间段条目数和内容卡片；卡片信息密度与列表页一致
- 交互约束：切换时间分组时保留当前定位；空归档时显示“暂无归档内容”占位及返回首页入口；不引入额外复杂可视化
- 验收口径：归档页是列表页的时间特化页，必须共享卡片、导航、页脚和双语文案槽位，不得设计为独立视觉体系

#### Public Page: About / Privacy / Terms
- 路由职责：承载品牌介绍、隐私政策、服务条款等静态内容，并提供双语运营文案展示能力
- 布局骨架：沿用公开站点导航和页脚；正文容器采用居中窄栏阅读布局，包含页面标题、更新时间、正文区和辅助返回入口
- 内容槽位：正文支持标题层级、段落、列表、链接和强调文本；若存在中英文版本，使用统一双语切换器而非双套页面结构
- 交互约束：语言切换只切换文案内容，不改变页面结构；正文过长时保留目录锚点或回到顶部入口；静态页缺内容时显示占位说明而非白屏
- 验收口径：About 强调产品定位与订阅价值；Privacy 与 Terms 必须提供更新时间、联系路径和回到首页入口

#### Public Page: 退订确认页
- 路由职责：承接邮件中的退订链接，在真正执行退订前明确目标邮箱、退订后果和确认动作
- 布局骨架：复用订阅弹窗的结果页视觉语言，但以页面形态呈现；核心区域包括状态标题、说明文案、目标邮箱、确认按钮、取消或返回首页按钮
- 内容槽位：必须能显示邮箱标识、请求状态提示、失败原因提示和帮助说明；若 token 无效或缺失，直接进入失败态规格
- 交互约束：确认操作为单一主 CTA；处理中时禁用重复提交；取消操作返回首页或来源页，不触发状态变更
- 验收口径：确认页必须显式区分“待确认”和“处理中”，避免用户误以为点击链接即已退订

#### Public Page: 退订成功页
- 路由职责：展示退订结果，告知用户该邮箱已停止接收后续邮件，并提供恢复浏览或重新订阅路径
- 布局骨架：延续退订确认页的结果容器；核心区域包括成功标题、结果说明、返回首页按钮、重新订阅入口
- 内容槽位：必须显示结果状态、目标邮箱或脱敏标识、结果生效说明和后续操作入口
- 交互约束：重复访问已完成链接时展示“已处理”说明，不重复写状态；失败或 token 失效时切换到失败态并给出恢复建议
- 验收口径：成功页不得只显示笼统 toast；必须形成独立页面级结果反馈，便于邮件链路验收与回放

### Task 3 共享组件映射基线
| 组件 | 适用页面 | 来源素材 | 最低实现约束 |
| --- | --- | --- | --- |
| 顶部导航与页脚 | 全部公开页 | 首页原型、详情页原型、`liquid_narrative/DESIGN.md` | 保持玻璃容器、主次导航层级、双语文案槽位和 Feed / API 预留入口 |
| 内容卡片 / 列表项 | 首页、列表页、Archive | 首页原型、`liquid_narrative/DESIGN.md` | 统一展示标题、来源、类型、发布时间、封面占位和点击热区 |
| 筛选条 / Tag Chips | 首页、列表页、后台内容页、后台工作流页 | 首页原型、后台截图、`liquid_narrative/DESIGN.md` | 使用 pill 形态，支持选中、高亮、无结果反馈 |
| 双语切换器 | 详情页、首页 / 列表 / 静态页运营文案区 | 详情页原型、`liquid_narrative/DESIGN.md`、PRD 5.1 | 支持中文单栏 / 中英双栏，首页等页面支持中英文文案切换 |
| 阅读进度条与悬浮订阅入口 | 详情页 | 详情页原型、`liquid_narrative/DESIGN.md` | 进度条使用 gradient，订阅入口悬浮但不遮挡正文 |
| 订阅表单反馈模块 | 订阅弹窗、退订页、详情页悬浮入口 | 订阅弹窗原型、`liquid_narrative/DESIGN.md` | 校验、提交中、成功、失败、重复订阅反馈文案必须可追踪 |
| 后台 KPI 卡片 / 表格 / 状态标签 | 五个后台页面 | 5 个后台截图、`liquid_narrative/DESIGN.md` | 锁定卡片密度、表格列层级、状态色和主操作位，不得随意改成纯表单流 |
| 后台确认弹窗 / Toast | 后台订阅者、内容、工作流、手动发布页 | 后台截图、`liquid_narrative/DESIGN.md` | 所有破坏性或异步操作都要有确认与结果反馈 |

### Task 3 状态映射基线
| 状态域 | 适用对象 | 必须覆盖的状态 | 事实来源 |
| --- | --- | --- | --- |
| 公开内容浏览 | 首页、列表页、Archive、静态页 | 默认、加载、空态、无结果、404 / 内容不存在 | PRD 5.1、8.5，Task 3 场景约束 |
| 详情阅读 | 详情页 | 默认、缺少译文、缺少原文、缺少封面、内容不存在 | PRD 5.1、8.5，Task 3 场景约束 |
| 订阅链路 | 订阅弹窗、悬浮订阅入口、退订页 | 邮箱无效、提交中、成功、失败、重复订阅、重复退订 | PRD 8.6，验收清单 2.6 |
| 后台数据查询 | 五个后台页面 | 默认、加载、空数据、错误 | PRD 5.2、8.7、8.8，后台截图 |
| 后台异步操作 | 发布、重试、删除 / 退订、微信草稿创建 | 确认中、提交中、成功、失败、可重试 | PRD 7.2、8.7、8.8，验收清单 2.7、2.8 |

### Task 3 缺失状态显式规格
#### Subscription States
- 邮箱无效：输入框失焦或提交时触发，使用表单级错误文案和错误色值提示；不关闭弹窗，不清空输入值
- 提交中：提交按钮进入 loading，输入框与关闭按钮按设计决定是否禁用；必须防止重复提交，并保留当前上下文
- 失败：保留用户输入，显示可重试提示和失败原因占位；不得将失败伪装成成功关闭
- 重复订阅：明确说明邮箱已存在于订阅名单，并提供继续浏览或直接关闭路径；不再创建重复记录
- 退订处理中 / 成功 / 重复退订 / token 失效：以页面级结果反馈呈现，必须能区分请求处理中、已成功退订、该链接已处理、链接无效或已过期四种结果

#### Public Browse States
- 空态：用于系统内暂无内容的场景，展示“暂无内容”说明、返回首页或稍后查看建议，并保留导航和订阅入口
- 无结果态：用于有内容但当前筛选无匹配结果的场景，保留当前筛选条件回显、结果数为 0 和清空筛选按钮
- 404 / 内容不存在：用于路由不存在或目标内容已下线的场景，提供错误说明、返回首页入口和继续浏览建议，不得白屏
- 加载态：首页、列表页、Archive 和静态页必须提供骨架屏或占位块，而不是仅显示浏览器空白；加载结束后保持布局稳定

#### Detail Fallback States
- 缺少译文：默认回退到原文单栏阅读，并明确告知“中文译文暂不可用”；阅读进度和免责声明仍需保留
- 缺少原文：允许仅展示中文内容，并隐藏或禁用原文跳转；不得出现空白双栏
- 缺少封面：回退到统一封面占位或纯文本标题头图样式，不影响正文和元信息排版
- 内容不存在：显示页面级错误说明、返回列表或首页入口，并保留站点导航

#### Admin States
- 加载态：仪表盘、订阅者、内容、工作流、手动发布页均需显示卡片骨架、表格占位或日志占位，避免主操作位跳动
- 空数据态：区分“尚未产生数据”和“筛选后无匹配结果”；前者给出引导动作，后者给出清空筛选或返回默认视图动作
- 错误态：显示接口失败或处理失败说明、可重试入口和必要的上下文，不吞掉错误
- 确认态：删除、退订、发布、重试、重跑、微信草稿创建等破坏性或异步操作都必须先展示确认弹窗或确认区
- 成功 / 失败反馈态：异步操作完成后用 toast、结果卡片或行内反馈明确告知结果；失败反馈必须保留重试或查看日志入口

### Task 3 前端验收矩阵
| 范围 | 页面 / 对象 | 布局与信息层级 | 视觉与 Token | 响应式 / 主题 | 交互与反馈 | 降级 / 异常 |
| --- | --- | --- | --- | --- | --- | --- |
| Public | 首页 | Hero、内容流、来源标签、订阅入口、页脚层级与原型一致 | 使用 Liquid Glass、Inter / Noto Serif、8px 间距体系、1120px 容器 | Desktop / Tablet / Mobile；Light / Dark | 标签切换、卡片点击、订阅入口可达 | 空态、无结果态需保留导航与返回路径 |
| Public | 详情页 | 标题、元信息、正文、阅读工具区、免责声明层级固定 | 中文正文使用 `article-body-cn`，进度条与强调色使用 gradient | Desktop / Tablet / Mobile；Light / Dark；单栏 / 双栏切换 | 双语切换、阅读进度、悬浮订阅入口、原文跳转 | 缺少译文 / 原文 / 封面时不破坏正文阅读与免责声明 |
| Public | 订阅弹窗 | 标题、说明、输入框、CTA、关闭按钮层级固定 | 使用浮层级别 blur、pill 按钮、表单错误态色值 | Desktop / Tablet / Mobile；Light / Dark | 校验、提交中、成功、失败、重复订阅反馈必须可见 | 关闭后可返回来源页；失败态保留重试入口 |
| Public | 列表页 | 筛选条、列表卡片、分页或加载更多、订阅入口 | 复用首页卡片与标签 token | Desktop / Tablet / Mobile；Light / Dark | 来源 / 类型 / 时间筛选与清空反馈明确 | 空态、无结果、404 需给出返回首页或清空筛选 |
| Public | Archive / About / Privacy / Terms | 静态内容容器、导航、页脚、双语文案槽位一致 | 复用公开站点玻璃容器、标题层级和排版 token | Desktop / Tablet / Mobile；Light / Dark | 语言切换或导航跳转清晰 | 内容缺失时显示占位说明，不得白屏 |
| Public | 退订确认 / 成功页 | 结果说明、主操作、返回首页入口层级清晰 | 复用订阅反馈和结果页 token | Desktop / Tablet / Mobile；Light / Dark | 处理中、成功、失败反馈明确 | 重复退订或 token 失效时给出恢复路径 |
| Admin | 仪表盘 | KPI、趋势、动态、系统状态、主操作位与截图一致 | 玻璃卡片、状态色、卡片密度与截图一致 | Desktop 优先；Tablet 可折叠；Light / Dark 待确认前按设计系统实现 | 刷新、跳转、卡片主操作反馈明确 | 空数据和错误态保留导航与重试 |
| Admin | 订阅者管理 | 搜索、筛选、表格、状态标签、操作位与截图一致 | 表格列宽、状态标签、按钮样式与截图一致 | Desktop 优先；Tablet 次级 | 搜索、排序、退订 / 删除确认、结果 Toast | 空表、接口错误、重复操作均需提示 |
| Admin | 内容管理 | 筛选、列表、状态、预览、发布 / 重试 / 手动录入入口固定 | 统一状态标签、类型标识、主次按钮层级 | Desktop 优先；Tablet 次级 | 发布确认、重试确认、预览跳转、反馈 Toast | 无译文、失败内容、无封面时显示降级标识 |
| Admin | 工作流监控 | 阶段状态、时间线、日志、重跑入口与截图一致 | 复用状态色、时间线层级、日志容器风格 | Desktop 优先；Tablet 次级 | 日志切换、按阶段筛选、重跑确认与反馈 | 无日志、部分阶段缺失、重跑失败时可追踪 |
| Admin | 手动发布 / 微信草稿 | 内容选择、手工输入、复用信息区、结果区层级清晰 | 表单、结果卡片、状态提示遵循截图和设计系统 | Desktop 优先；Tablet 次级 | 已发布内容选择、提交中、成功、失败、重试 | 微信接口失败不得影响站内已发布内容 |

### Requirement: 需求与验收必须一一映射
实施计划 SHALL 将每一项 P0 需求映射到至少一个可验证的交付任务和验收检查点，确保需求、实现、验证之间可追踪。

#### Scenario: 建立任务与验收映射
- **WHEN** 团队编写实施任务
- **THEN** 每个任务必须对应用户可见能力或关键基础能力
- **AND** 任务必须标注其依赖关系、验证方式和完成标准
- **AND** 验收清单必须覆盖内容发现、去重、抓取、抽取、翻译、Web 展示、订阅、后台、微信、环境与外部集成

### Requirement: Task4 必须锁定数据模型、API、工作流、重试与集成边界
Task4 SHALL 以 `docs/delivery/Database-Design.md`、`docs/delivery/API-Design.md`、`docs/delivery/System-Architecture.md` 为唯一事实来源，输出一套可直接指导 Django/Wagtail、Celery 和外部适配器实现的边界清单，避免开发阶段再次猜测表结构、接口分区、阶段职责和失败恢复方式。

#### Scenario: 锁定数据模型与存储分层
- **WHEN** 团队执行 Task4 的数据边界梳理
- **THEN** 必须至少锁定 `tb_source`、`tb_source_endpoint`、`tb_discovery_run`、`tb_discovery_run_source_stat`、`tb_content_item`、`tb_content_artifact`、`tb_run_log`、`tb_subscriber`、`tb_email_digest_batch`、`tb_email_digest_batch_item`、`tb_email_delivery`、`tb_publish_record`、`tb_wechat_draft_detail`、`tb_content_page_snapshot`、`tb_home_page`、`tb_listing_page`、`tb_static_page` 的职责和关系
- **AND** 必须明确 PostgreSQL 只承载结构化业务真相，COS 只承载 `raw_html`、原始响应、字幕、音频、图片和调试导出等大对象
- **AND** 必须明确 `dedupe_key`、`web_slug`、`unsubscribe_token`、`provider_message_id`、`wechat_draft_id` 等关键唯一键或外部关联键的归属位置

#### Scenario: 锁定 API 分区与集成入口
- **WHEN** 团队执行 Task4 的接口边界梳理
- **THEN** 必须明确 `/api/public/*`、`/api/admin/*`、`/api/integrations/*` 三类接口分区及其认证规则、CSRF 规则和错误码口径
- **AND** 必须明确订阅创建、手动 URL 导入、纯手工内容创建、启动翻译、Web 发布、微信草稿创建 / 重试、每日汇总发送等接口需要 `Idempotency-Key`
- **AND** 必须明确 Resend Webhook 属于第三方回调边界，不与后台人工操作接口混用

#### Scenario: 锁定工作流阶段输入输出与重试矩阵
- **WHEN** 团队执行 Task4 的工作流边界梳理
- **THEN** 必须明确 `discover -> fetch -> extract -> transcribe -> translate -> research -> review_pending -> publish -> notify` 每个阶段的输入、输出、状态写回位置和产物归属
- **AND** 必须明确 `discover` 以 `tb_discovery_run` / `tb_discovery_run_source_stat` 为主追踪对象，其余内容处理阶段以 `tb_content_item` + `tb_run_log` 为主追踪对象
- **AND** 必须明确内容级可重试阶段仅包括 `fetch`、`extract`、`transcribe`、`translate`、`research`、`publish`、`notify`
- **AND** 必须明确通知失败不得回滚 Web 已发布状态，微信草稿失败不得阻断主站发布

#### Scenario: 锁定外部集成责任边界
- **WHEN** 团队执行 Task4 的集成边界梳理
- **THEN** 必须明确 Source Adapters 只负责发现与抓取外部来源，Extractors 只负责结构化抽取，Media / ASR 只负责音频与转录，LLM 只负责翻译与研究报告
- **AND** 必须明确 Resend 只负责邮件发送与投递状态回写，微信接口只负责草稿生成，GA4 只负责事件注入与统计，不参与业务主流程状态流转
- **AND** 必须明确所有外部集成失败都要回写 `tb_run_log` 或对应记录表，并保留可追溯的错误码、请求摘要和响应摘要

#### Task4 Boundary Matrix
| Boundary Area | Locked Scope | System Of Record / Entry | Out Of Scope Or Guardrail |
| --- | --- | --- | --- |
| Content sources | `tb_source` + `tb_source_endpoint` define source metadata, discovery strategy, endpoint config, schedule binding | PostgreSQL tables, referenced by discovery scheduler and source adapters | Do not store raw payload blobs in source tables |
| Discovery runs | `tb_discovery_run` + `tb_discovery_run_source_stat` track one execution and per-source stats | PostgreSQL, primary tracker for `discover` | Do not overload as content lifecycle tracker |
| Content lifecycle | `tb_content_item` is the canonical content record, `tb_run_log` records stage attempts, `tb_content_artifact` stores derived artifacts metadata | PostgreSQL, primary tracker for `fetch` through `notify` | Do not split stage truth across ad hoc tables |
| Publish and page state | `tb_publish_record`, `tb_wechat_draft_detail`, `tb_content_page_snapshot` record Web publish, WeChat draft, rendered snapshot | PostgreSQL for structured publish truth, COS for large snapshot payloads when needed | WeChat draft status must not block Web publish completion |
| Subscriber and delivery | `tb_subscriber`, `tb_email_digest_batch`, `tb_email_digest_batch_item`, `tb_email_delivery` cover subscription, digest assembly, provider delivery result | PostgreSQL, with Resend callback writing provider status back | Delivery failure does not roll back published content |
| CMS page config | `tb_home_page`, `tb_listing_page`, `tb_static_page` hold Wagtail-managed page config and content slots | PostgreSQL via Wagtail models | Do not mix workflow runtime data into page config models |
| Blob storage | Raw HTML, external responses, subtitles, audio, images, debug exports live in COS | COS object storage, referenced by artifact metadata in PostgreSQL | PostgreSQL stores metadata and keys only, not large blobs |
| External keys | `dedupe_key`, `web_slug`, `unsubscribe_token`, `provider_message_id`, `wechat_draft_id` stay on owning domain tables | Canonical key lives on the table that owns the business action | Do not duplicate writable copies across unrelated tables |

#### Task4 Retry And Recovery Matrix
| Stage | Primary Tracker | Retry Allowed | Recovery Rule |
| --- | --- | --- | --- |
| `discover` | `tb_discovery_run` + `tb_discovery_run_source_stat` | No content-level retry | Re-run as a new discovery execution |
| `fetch` | `tb_content_item` + `tb_run_log` | Yes | Retry fetch without resetting downstream published state |
| `extract` | `tb_content_item` + `tb_run_log` | Yes | Retry after parser fix or source payload refresh |
| `transcribe` | `tb_content_item` + `tb_run_log` | Yes | Retry when media or ASR dependency recovers |
| `translate` | `tb_content_item` + `tb_run_log` | Yes | Retry without losing prior source artifacts |
| `research` | `tb_content_item` + `tb_run_log` | Yes | Retry after prompt, model, or quota issue recovery |
| `review_pending` | `tb_content_item` | No | Manual review gate, not an automated retry stage |
| `publish` | `tb_content_item` + `tb_publish_record` | Yes | Retry publish independently from notify or WeChat draft |
| `notify` | `tb_content_item` + `tb_email_delivery` | Yes | Notify failure only affects delivery records, not Web publish |

#### Task4 Integration Responsibility Matrix
| Integration | Responsibility | Call Direction | Failure Recording |
| --- | --- | --- | --- |
| Source Adapters | Discover candidates and fetch remote source payloads | Scheduler / admin action -> adapter -> external source | `tb_run_log` with source, endpoint, request summary, response summary |
| Extractors | Convert fetched payload into normalized structured fields | Pipeline worker -> extractor | `tb_run_log` with parser version and error details |
| Media / ASR | Download media, extract audio, request transcript | Pipeline worker -> media utility / ASR provider | `tb_run_log` plus artifact record for transcript output |
| LLM | Translate and generate research summary | Pipeline worker -> LLM provider | `tb_run_log` with prompt summary, model, failure code |
| COS | Persist large artifacts and debug exports | App / worker -> COS | Artifact metadata plus storage error in `tb_run_log` |
| Resend | Send digest / transactional mail and receive webhook status | App -> Resend, Resend webhook -> integrations API | `tb_email_delivery` plus webhook processing log |
| WeChat | Create and retry manual draft | Admin action / worker -> WeChat API | `tb_wechat_draft_detail` plus `tb_run_log` |
| GA4 | Emit analytics events after user-facing interactions | Public / admin app -> GA4 | Non-blocking app log; must not alter business state |

### Requirement: 实施顺序必须遵循先基线后开发
系统实施 SHALL 先完成文档基线、数据与接口边界、前端保真约束和验收映射，再进入工程初始化与功能开发。

#### Scenario: 制定实施顺序
- **WHEN** 团队输出开发路线
- **THEN** 必须优先完成需求对齐、信息缺口确认、数据模型与 API 边界锁定、前端页面与组件映射
- **AND** 之后再进入 Django/Wagtail 工程初始化、核心模型落库、公开站点、后台、流水线、发布与通知能力建设

#### Task5 Implementation Order
| Phase | Objective | Minimum Deliverable | Exit Check |
| --- | --- | --- | --- |
| 0. Preconditions | Close Task1 gaps or obtain explicit waiver; finish Task3 and Task4 baseline artifacts | Signed-off gap list, front-end mapping, Task4 matrices | No unresolved blocker without owner and decision |
| 1. Project bootstrap | Initialize Django, Wagtail, Celery, PostgreSQL, Redis, COS config, base settings split, env template, health checks | Runnable project skeleton with local startup guide | App boots, migrations run, worker and beat start |
| 2. Core models and auth | Land core models, admin auth, Wagtail page models, basic audit / run log scaffolding | Initial migrations, admin login, base model registration | Core schema migrates cleanly and admin login works |
| 3. Public site | Build home, listing, detail, Archive, About, Privacy, Terms, subscribe / unsubscribe flow | Public pages render from seeded data with fallback states | Public routing, SEO basics, subscribe loop pass |
| 4. Admin console | Build dashboard, source management, content management, subscriber view, workflow monitor, manual intake | Operators can inspect content and trigger core actions | CRUD and operator feedback states work end-to-end |
| 5. Pipeline and review | Implement discover, fetch, extract, transcribe, translate, research, review_pending transitions | Replayable pipeline job path with run logs and artifacts | Sample content completes to review queue |
| 6. Publish and notify | Implement Web publish, snapshot, digest batch, email delivery, WeChat draft tool | One content item publishes to Web and enters digest flow | Publish and notify rules match Task4 recovery boundary |
| 7. Integration validation | Validate external providers, observability, failure recovery, acceptance replay | Environment checklist, smoke scripts, validation report | Acceptance-critical flows verified with evidence |

#### Task5 Stage Deliverables
| Stage | Must Be Demonstrable |
| --- | --- |
| Bootstrap | Local developer can start app, worker, beat, PostgreSQL, Redis with documented env vars |
| Core models and auth | Schema, admin login, base permissions, audit fields, run log infrastructure |
| Public site | Seeded content can render target pages and all required fallback states |
| Admin console | Operator can manage sources, inspect content, review workflow, and create manual entries |
| Pipeline and review | Replay sample can produce artifacts and stage logs with deterministic status transitions |
| Publish and notify | Web publish remains successful even when mail or WeChat draft fails |
| Integration validation | Mock and real-provider checks are separated, and blockers are visible before release |

### Requirement: Task6 必须建立需求到验证的一一映射
Task6 SHALL 将 PRD P0、Task2-Task5 产物和 `docs/delivery/Acceptance-Checklist.md` 串成一张需求到验证映射表，确保每个关键能力都存在负责人明确、输入清晰、结果可复核的验证动作。

#### Scenario: 输出需求到验证映射
- **WHEN** 团队执行 Task6 的验收映射梳理
- **THEN** 必须为每项 P0 需求标注对应实现任务、验证动作、验证环境、证据载体和阻断级别
- **AND** 必须明确哪些验证使用 mock、哪些验证需要真实外部联调、哪些项目属于上线前阻断项
- **AND** 未形成映射前不得宣称“可验收”或“可上线”

#### Task6 Requirement-To-Validation Mapping
| Requirement Slice | Implementation Anchor | Validation Action | Validation Mode | Release Gate |
| --- | --- | --- | --- | --- |
| Public pages: home, listing, detail, Archive, About, Privacy, Terms | Task3 page mapping + Task5 public site | Route smoke test, content rendering check, empty / 404 / fallback review | Local + seeded data | Blocker |
| Subscription flow: subscribe, duplicate, invalid email, unsubscribe | Task3 state spec + Task5 public site + delivery models | API check, form state verification, unsubscribe token path check | Local + mock mail, real link format | Blocker |
| Admin login and dashboard | Task5 core auth + admin console | Role login check, dashboard load, empty / error state review | Local / staging | Blocker |
| Source management and manual intake | Task4 source boundary + Task5 admin console | CRUD verification, URL import, manual creation, validation errors | Local / staging | Blocker |
| Workflow pipeline: discover through review_pending | Task4 workflow matrix + Task5 pipeline | Replay sample, stage transition audit, artifact existence check | Local + selected real sample | Blocker |
| Publish to Web | Task4 publish boundary + Task5 publish stage | Publish action, page snapshot, Web visibility, rollback boundary check | Staging | Blocker |
| Email digest and delivery callbacks | Task4 notify boundary + Task5 publish/notify | Digest assembly, send dry run, callback write-back check | Mock first, real provider before release | Blocker |
| WeChat draft tool | Task4 integration matrix + Task5 publish/notify | Draft creation / retry verification, failure non-blocking check | Mock first, real provider before release | Blocker |
| Observability and failure logs | Task4 run-log boundary + Task5 all stages | Inspect `tb_run_log`, error summaries, retry evidence | Local / staging | Blocker |
| Analytics injection | Task4 GA4 boundary + public/admin implementation | Event emission spot check without affecting core flow | Mock or staging instrumentation | Non-blocker before first code merge, blocker before production |

#### Task6 Validation Mode Matrix
| Validation Target | Mock Allowed | Real Integration Required | Evidence |
| --- | --- | --- | --- |
| Page rendering, layout fallback, form state | Yes | No | Screenshots, route checklist, seeded content results |
| Pipeline stage transitions and retries | Yes for failure injection | Yes for at least one representative content sample | Run log export, artifact keys, status history |
| Subscription and unsubscribe token chain | Yes for provider send | Yes for real token link shape and callback contract | API responses, token record, callback sample |
| Email delivery provider callback | Yes in early phase | Yes before release | Delivery record update, webhook payload sample |
| WeChat draft creation | Yes in early phase | Yes before release | Draft ID record, retry result, error sample |
| COS artifact persistence | Yes for local adapter | Yes before release | Stored object key, retrieval check, error log |
| GA4 event injection | Yes | Recommended before release | Event capture sample or staging debug view |

## MODIFIED Requirements
### Requirement: 邮件通知策略
系统 SHALL 以每日汇总邮件作为 MVP 唯一默认通知策略，周报、标签订阅和个性化订阅仅作为 P1 增强项保留。

#### Scenario: 发布后通知
- **WHEN** 内容被管理员发布到公开站点
- **THEN** 系统应将内容纳入对应日期的 digest 候选集合
- **AND** 邮件发送失败不得回滚内容已发布状态

### Requirement: 手动录入内容 schema
系统 SHALL 将后台手动录入统一定义为两种模式：URL 自动抓取导入与纯手工录入；纯手工录入至少包含来源信息、原文标题、中文标题、原文正文、中文正文，并允许补充摘要、作者和发布时间。

#### Scenario: 运营者录入外部内容
- **WHEN** 管理员在后台选择手动录入
- **THEN** 系统必须允许选择 URL 导入或纯手工录入
- **AND** 纯手工录入内容应直接进入统一审核发布链路

## REMOVED Requirements
### Requirement: 自动公众号主流程发布
**Reason**: 当前 PRD 已明确微信公众号发布不再属于自动主流程，避免平台能力影响主站交付与运营稳定性。
**Migration**: 所有公众号相关能力统一迁移为后台独立的手动草稿工具，并记录 `wechat_draft_id`、错误码与重试结果。
