# MAS ERP V2 Protocol

## Purpose
MAS ERP V2 is the rebuilt ERP test project for AI-First WF. It uses one project runtime domain, `test.mas-erp.com`, and treats every screen as a route inside that project, not as a separate subdomain.

## Runtime
- Project slug: `mas-erp`
- Service: `mas-erp-v2`
- Local port: `9010`
- Public URL: `https://test.mas-erp.com`
- Upstream source of truth: `https://ai-auto.cloud`
- Frontend engine: MAS Core V2
- Data engine: MasStore V3 / WS3 contract
- Backend contract: Quantum document APIs and `/API/v7`

## Screens
- `/#/dashboard`: service health, KPIs, latest invoices
- `/#/masters`: schema-driven CRUD for accounts, items, warehouses
- `/#/sales`: sales invoice header/detail editor
- `/#/purchase`: purchase invoice header/detail editor
- `/#/inventory`: inventory movement and item-card workbench
- `/#/finance`: trial balance, profit/loss, balance sheet workbench

## MasStore V3 Contract
MasStore V3 owns all browser data access:
- `read(name, options)` for table reads
- `schema(name)` for column discovery
- `save(table, records)` for auto CRUD
- `fun(name, params)` for SQL/report functions
- `proc(name, params)` for procedures
- `documentProfile(headTable)` for document UI shape
- `documentDefaults(headTable, header)` for default header values
- `saveDocumentDraft(options)` for draft header/detail save
- `finalizeDocument(options)` for posting/finalization

## Quantum Contract
The service proxy exposes:
- `GET /health`
- `POST /api/v7`
- `GET /api/document-profile`
- `GET /api/document-defaults`
- `POST /api/document-search`
- `POST /api/document-draft-save`
- `POST /api/document-finalize`

## Important Fix
The original document engine could not save draft invoices when `sequence.allocate_on = finalize` and the table column `doc_no` is `NOT NULL`. The core rule is now:

If the sequence field is required, allocate sequence during draft save even if the profile says allocation is normally on finalize.

This preserves real draft saves while keeping finalization behavior intact.

## AI-First Selection Rules
- Select the project for architecture or cross-module changes.
- Select `mas-store-v3` when the issue is data, CRUD, functions, procedures, caching, or document save.
- Select `erp-app` when the issue is UI flow, route state, invoice editing, reports, or gkeys.
- Select `server` when the issue is service health, proxy behavior, API contract, or CORS.
- Select `dashboard-kit-v2` and `styles` when the issue is layout or reusable dashboard controls.

## Required Tests
- Syntax: `npm run check` in `/srv/apps/ai-first/mas-erp/_generated`
- Local health: `curl http://127.0.0.1:9010/health`
- Public health: `curl https://test.mas-erp.com/health`
- Browser smoke: open dashboard, masters, and sales routes with Playwright
- Document smoke: call `/api/document-draft-save` with `sales_invoice_hd` and one line
