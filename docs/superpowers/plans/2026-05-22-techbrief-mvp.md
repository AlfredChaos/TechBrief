# TechBrief MVP Implementation Plan

> For agentic workers: execute task-by-task and keep the public Web, admin backend, and workflow boundaries aligned with `TechBrief-PRD.md`.

**Goal:** Build a runnable TechBrief MVP as a public Chinese Web blog for OpenAI / Anthropic content, extended public video platform materials, daily digest email subscriptions, workflow visibility, admin review / publish controls, and a manual WeChat draft publishing tool in the admin console.

**Architecture:** A stage-based content pipeline discovers public article and video materials, persists intermediate artifacts and logs, generates reviewable Chinese content, transcribes audio when videos lack subtitles, creates research reports from those transcripts, and exposes two product surfaces: a public Web site and an authenticated admin console. Daily digest email notifications and WeChat draft publishing are isolated adapters so they do not block the core Web publishing flow.

**Tech Stack Direction:** Python 3.14, uv, HTTP client + extraction libraries, SQLite for MVP, Web framework for public/admin pages, email adapter, optional job runner / scheduler.

---

## Product Surfaces

- Public Web: home, content list, content detail, email subscribe / unsubscribe
- Admin Console: dashboard, subscriber list, content list / detail, daily run status, manual publish actions
- Workflow Engine: discover, fetch, extract, translate / transcribe / research, review draft, publish web, notify email
- Manual Channel Tooling: create WeChat draft from existing published content or manually entered content

---

## Task 1: Initialize Web Project Baseline

**Outcome:** A runnable project skeleton exists for public Web pages, admin pages, shared backend services, and background workflow entrypoints.

- [ ] Create project configuration, dependency manifests, and environment example
- [ ] Define backend / frontend directory structure
- [ ] Add formatting, linting, and test configuration
- [ ] Verify the chosen package managers and runtime versions

## Task 2: Define Core Data Model

**Outcome:** The system can persist content items, subscribers, publish records, and run logs.

- [ ] Model `ContentItem`, `Subscriber`, `PublishRecord`, and `RunLog`
- [ ] Add dedupe strategy for article / video / manual content
- [ ] Add migration or schema bootstrap flow for SQLite MVP
- [ ] Add focused tests for dedupe and status transitions

## Task 3: Build Source Discovery Layer

**Outcome:** The system can discover OpenAI / Anthropic public article entries and related video entries across more public video platforms.

- [ ] Implement source adapters for articles and videos
- [ ] Expand video discovery to more public video platforms
- [ ] Support RSS where available and list-page polling as fallback
- [ ] Capture canonical URL or source item ID for dedupe
- [ ] Persist discovery result logs

## Task 4: Build Fetch / Extract Layer

**Outcome:** The system can save raw content and derive structured inputs for translation and research.

- [ ] Save raw HTML and source metadata for articles
- [ ] Save video metadata and subtitle / transcript text when available
- [ ] Extract audio and transcribe videos when subtitles are missing
- [ ] Extract structured content blocks and key metadata
- [ ] Add regression checks for extraction failures and fallback states

## Task 5: Build Translation and Quality Checks

**Outcome:** The system produces reviewable Chinese content and, for subtitle-free videos, research reports that preserve structure and technical accuracy.

- [ ] Add glossary loading and term consistency rules
- [ ] Implement translation adapter with retry behavior
- [ ] Implement research report generation from transcribed video text
- [ ] Preserve code blocks, inline code, links, and section hierarchy
- [ ] Add minimal structure parity checks

## Task 6: Build Public Web Publishing Flow

**Outcome:** Reviewed content can be published to the public Web site.

- [ ] Render content for public article / video detail pages
- [ ] Implement home and list pages
- [ ] Add content status flow: `review_pending` -> `published`
- [ ] Inject source attribution and disclaimer footer

## Task 7: Build Email Subscription Flow

**Outcome:** Users can subscribe and unsubscribe by email, and published content can trigger daily digest notifications.

- [ ] Add subscription form and subscriber storage
- [ ] Add unsubscribe flow
- [ ] Implement daily digest email jobs with mock-first support
- [ ] Track delivery status and retry failures

## Task 8: Build Admin Console

**Outcome:** Operators can manage subscribers, content, and workflow runs from one backend.

- [ ] Add dashboard metrics for daily runs and content volume
- [ ] Add subscriber list view
- [ ] Add content list / detail / preview view
- [ ] Add daily workflow execution view with failure details
- [ ] Add retry actions from failed stage

## Task 9: Build Manual Content Publishing

**Outcome:** Operators can publish other articles outside the automatic discovery pipeline.

- [ ] Add manual URL import flow with auto-fetch
- [ ] Add manual rich-text content creation flow
- [ ] Reuse the same review / publish states as auto-discovered content
- [ ] Audit manual publish actions in logs

## Task 10: Build Manual WeChat Draft Tool

**Outcome:** Admin users can manually create WeChat drafts without coupling the feature to the main publishing pipeline.

- [ ] Add admin page for WeChat draft creation
- [ ] Support generating a draft from published Web content while reusing cover, summary, and author fields
- [ ] Support manually entered title / author / body content
- [ ] Persist `wechat_draft_id`, response summary, and retry status
- [ ] Provide mock mode for environments without real credentials

## Task 11: Validation and Handoff

**Outcome:** The MVP can be demonstrated end-to-end against the updated acceptance checklist.

- [ ] Replay 10 historical items across both sources and both content types
- [ ] Verify Web publishing, email subscription, admin observability, and manual WeChat draft creation
- [ ] Run focused tests for dedupe, retry, publish, and subscription flows
- [ ] Update delivery notes with exact commands and known limitations

---

## Spec Coverage Self-Review (PRD v0.2)

- Public product shape now centers on a Web blog, not WeChat as the default distribution endpoint.
- Daily digest email subscriptions and admin operations are first-class MVP requirements.
- WeChat integration is preserved as an admin-side manual publishing tool.
- Article and video materials are both included in scope, with transcription and research-report fallback behavior for missing subtitles.
