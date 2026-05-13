# AI-First Vibe Protocol

## Current Decision

AI-First treats an application as a logical runtime tree, not as loose files. The
project owns one runtime domain or one domain per real microservice. Pages,
screens, APIs, and components are routes under that runtime; they do not get
fake subdomains.

## Tree Model

The active tree is:

`project -> service/pages/modules -> components -> bulks`

The database supports deeper bulk nesting through `pillar.parent_pillar_id`,
`pillar.node_path`, and `pillar.role`. The UI renders nested bulks when present,
but the default ingestion strategy for large legacy files is sequential semantic
bulks with original `line_start` and `line_end`. That keeps selection atomic
without pretending every chunk is a standalone JavaScript file.

## Selection Protocol

Selection is normalized before any prompt packet is built:

- Selecting a project parent covers its descendants and removes duplicated child
  selectors.
- Selected pages resolve to their source component bulks.
- Selected components expand to their bulks.
- Selected bulks are the smallest editable unit.
- Duplicate `project/component/bulk` labels are excluded with
  `duplicate_parent_child_selection`.
- Search rules filter selected bulks by name, class, language, or content.

Search examples:

- `component:sales-invoice class:mas-ui`
- `content:warehouse finalize`
- `lang:sql sales_invoice_hd`

## Code Context

Every code item in the prompt packet is line-numbered:

`relative_line | absolute_line | code`

`mini` mode keeps the head and tail with hidden-line markers. `full` mode keeps
the entire selected bulk. Syntax checks run at component/full-source level,
because atomic bulks can be partial functions, IIFEs, or SQL files.

## Prompt Packet

`POST /api/platform/prompt-packet` returns:

- system instructions
- selected project profile and system/planner MD
- classification instructions
- selected code context
- raw prompt
- available agents

The raw prompt is the exact text that can be sent to Bedrock or another model.

## Planner Simulation

`POST /api/platform/planner/simulate` builds and persists:

- `planner_run`
- normalized attention scope
- excluded/noise report
- agent-owned micro-tasks in `agent_task_assignment`
- required verification plan

The simulation is deterministic and does not edit code. It is used to test the
A2A contract before wiring live model execution.

## Agents

Default agents:

- `planner`: orchestration and context selection
- `mas-ui`: MAS Core V2/QDML UI and gkeys
- `mas-store`: frontend data, session, cache, WS3/store contracts
- `backend-api`: HTTP APIs, services, auth, curl contracts
- `postgres`: SQL, procedures, indexes, integrity
- `quantum-core`: platform/runtime/protocol changes
- `qa-browser`: Playwright and curl verification

Classifications decide the default owner, but the planner can split one request
across multiple agents when the selected code crosses boundaries.

## Test Protocol

Projects can define:

- `auth_script`: Playwright setup before a page test
- `test_case` with `runner_type=playwright`
- `test_case` with `runner_type=curl`
- `test_run` with captured result, stdout/stderr, screenshot path, bad responses,
  failed requests, console errors, and console warnings

Auth credentials can store references to local env secrets. The runner resolves
them server-side and does not print the resolved secret.

## AI-Auto ERP Seed

Project `erp` is now seeded from the real `/srv/apps/ai-auto` codebase:

- Quantum runtime and `/API/v7`
- document-profile and document-service
- MAS API V2, MAS Store V2, MAS UI V2, bridges, mobile kit
- document host and sales invoice screen
- inventory, financial, and report SQL
- platform-admin/domain pipeline code
- `accounting_core_schema_v1.json`

Runtime: `https://ai-auto.cloud`

Screens are routes:

- `/document-host.html?head_table=sales_invoice_hd&mode=preview`
- `/platform-admin.html`
- `/dashboard.html`
- `/report-host.html`

No page/component subdomains are used.

## Arabic Summary

البروتوكول الحالي يعتبر المشروع كيانا شجريا: مشروع ثم خدمة/صفحات/موديولات ثم
مكونات ثم bulks. الدومين للمشروع أو الميكروسيرفس الحقيقي فقط، أما الصفحات
والمكونات فهي routes داخل التطبيق. الاختيار يتم تنظيفه قبل الإرسال للـ AI حتى
لا يتكرر الأب والابن في نفس الطلب. الـ mini code مرقم بأسطر نسبية ومطلقة،
والـ syntax يفحص المصدر الكامل للمكون لا كل bulk منفصل، لأن bulk قد يكون جزءا
من function أو IIFE. planner simulation تحفظ خطة وmicro-tasks حسب الوكلاء
بدون تعديل الكود، وPlaywright/curl هما بروتوكول التحقق المباشر.
