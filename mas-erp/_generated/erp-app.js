;(function (global) {
  "use strict";

  const { D, app } = global.MAS;
  const Kit = global.MasDashboardKit;
  const store = global.MasStoreV3.create({ apiBase: "", tenantId: 3, branchId: 1, userId: 1 });

  const SESSION = { company_id: 3, branch_id: 1, user_id: 1, user_name: "mas-erp-v2" };
  const ROUTES = {
    dashboard: "لوحة القيادة",
    masters: "البيانات الأساسية",
    sales: "فواتير البيع",
    purchase: "فواتير الشراء",
    inventory: "تقارير المخزون",
    finance: "التقارير المالية"
  };
  const MASTER_TABLES = {
    accounts: {
      table: "fin_accounts",
      title: "شجرة الحسابات",
      fields: ["code", "name", "account_type", "report_type", "normal_balance", "is_postable", "is_active"],
      defaults: { tenant_id: 3, account_type: "asset", report_type: "balance_sheet", normal_balance: "debit", is_postable: true, is_active: true }
    },
    items: {
      table: "inv_items",
      title: "الأصناف",
      fields: ["code", "name", "item_type", "uom_id", "sales_price", "cost_price", "is_sales", "is_purchase", "is_active"],
      defaults: { tenant_id: 3, item_type: "stock", uom_id: 9, sales_price: 0, cost_price: 0, is_sales: true, is_purchase: true, is_active: true }
    },
    warehouses: {
      table: "inv_warehouses",
      title: "المخازن",
      fields: ["code", "name", "warehouse_kind", "branch_id", "is_active"],
      defaults: { tenant_id: 3, branch_id: 1, warehouse_kind: "general", is_active: true }
    }
  };

  function routeFromHash() {
    const value = (location.hash || "#/dashboard").replace(/^#\/?/, "");
    return ROUTES[value] ? value : "dashboard";
  }

  function rowId(row) {
    return row && (row.ID || row.id || row.Id || "");
  }

  function idOf(value) {
    if (value && typeof value === "object") return value.id || value.ID || value.Id || "";
    return value == null ? "" : value;
  }

  function labelOf(value) {
    return global.MasStoreV3.labelOf(value);
  }

  function money(value) {
    const number = Number(value || 0);
    return number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function safeText(value) {
    if (value == null) return "";
    if (typeof value === "object") return labelOf(value);
    return String(value);
  }

  function pickRows(payload) {
    return global.MasStoreV3.rows(payload);
  }

  function firstCollection(profile) {
    return profile && Array.isArray(profile.collections) ? profile.collections.find((item) => item && item.type === "items") || profile.collections[0] : null;
  }

  function initialDocState(kind) {
    return {
      headTable: kind === "purchase" ? "purch_invoice_hd" : "sales_invoice_hd",
      defaults: {},
      preview: {},
      profile: null,
      header: {
        tenant_id: 3,
        branch_id: 1,
        entity_id: kind === "purchase" ? "" : "66",
        warehouse_id: "10",
        currency_id: "1",
        exchange_rate: 1,
        doc_date: today(),
        posting_date: today(),
        due_date: today(),
        status: "draft",
        remarks: `MAS ERP V2 ${kind} draft`
      },
      lines: [store.emptyLine()],
      saving: false,
      result: null,
      error: ""
    };
  }

  const state = {
    route: routeFromHash(),
    title: ROUTES[routeFromHash()],
    loading: false,
    status: "",
    error: "",
    health: null,
    rows: {
      fin_accounts: [],
      inv_items: [],
      inv_warehouses: [],
      sales_invoice_hd: [],
      purch_invoice_hd: []
    },
    schemas: {},
    profiles: {},
    masterTab: "accounts",
    masterForm: Object.assign({ code: `MAS-${Date.now().toString(36).slice(-5)}`, name: "" }, MASTER_TABLES.accounts.defaults),
    masterEditId: "",
    doc: {
      sales: initialDocState("sales"),
      purchase: initialDocState("purchase")
    },
    reports: {
      trialBalance: [],
      profitLoss: {},
      balanceSheet: {},
      inventory: [],
      apiChecks: []
    }
  };

  function currentState(ctx) {
    return (ctx && ctx.db) || (ctx && typeof ctx.getState === "function" ? ctx.getState() : {}) || {};
  }

  async function capture(label, task) {
    try {
      return { label, ok: true, value: await task };
    } catch (error) {
      return { label, ok: false, error: error && error.message ? error.message : String(error) };
    }
  }

  async function loadDocument(ctx, kind) {
    const db = currentState(ctx);
    const current = db.doc[kind];
    const profile = await store.documentProfile(current.headTable).catch(() => null);
    const defaults = await store.documentDefaults(current.headTable, current.header).catch(() => ({}));
    const nextHeader = Object.assign({}, current.header, defaults.defaults || {});
    if (defaults.preview && defaults.preview.doc_no) nextHeader.doc_no = defaults.preview.doc_no;
    const doc = Object.assign({}, db.doc, {
      [kind]: Object.assign({}, current, {
        profile,
        defaults: defaults.defaults || {},
        preview: defaults.preview || {},
        header: nextHeader
      })
    });
    ctx.set({ doc });
  }

  async function refresh(ctx) {
    ctx.set({ loading: true, error: "", status: "loading live ERP data" });
    const checks = await Promise.all([
      capture("health", fetch("/health").then((r) => r.json())),
      capture("fin_accounts", store.read("fin_accounts", { options: { DataOnly: true, top: 80 } })),
      capture("inv_items", store.read("inv_items", { options: { DataOnly: true, top: 80 } })),
      capture("inv_warehouses", store.read("inv_warehouses", { options: { DataOnly: true, top: 40 } })),
      capture("sales_invoice_hd", store.read("sales_invoice_hd", { options: { DataOnly: true, top: 40 } })),
      capture("purch_invoice_hd", store.read("purch_invoice_hd", { options: { DataOnly: true, top: 40 } })),
      capture("schema:fin_accounts", store.schema("fin_accounts")),
      capture("schema:inv_items", store.schema("inv_items")),
      capture("schema:inv_warehouses", store.schema("inv_warehouses")),
      capture("sales_profile", store.documentProfile("sales_invoice_hd")),
      capture("purchase_profile", store.documentProfile("purch_invoice_hd"))
    ]);
    const db = currentState(ctx);
    const next = { rows: Object.assign({}, db.rows), schemas: Object.assign({}, db.schemas), profiles: Object.assign({}, db.profiles), reports: Object.assign({}, db.reports), health: db.health };
    checks.forEach((item) => {
      if (!item.ok) return;
      if (item.label === "health") next.health = item.value;
      else if (item.label.indexOf("schema:") === 0) next.schemas[item.label.split(":")[1]] = item.value;
      else if (item.label === "sales_profile") next.profiles.sales = item.value;
      else if (item.label === "purchase_profile") next.profiles.purchase = item.value;
      else next.rows[item.label] = item.value;
    });
    next.reports = buildReports(next.rows);
    ctx.set(Object.assign({}, next, { loading: false, status: "ready", error: checks.filter((item) => !item.ok).map((item) => `${item.label}: ${item.error}`).join("\n") }));
    await loadDocument(ctx, "sales");
    await loadDocument(ctx, "purchase");
  }

  function buildReports(rows) {
    const accounts = rows.fin_accounts || [];
    const sales = rows.sales_invoice_hd || [];
    const purchase = rows.purch_invoice_hd || [];
    const items = rows.inv_items || [];
    const byType = accounts.reduce((acc, row) => {
      const type = safeText(row.account_type || "unknown");
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {});
    const salesTotal = sales.reduce((sum, row) => sum + Number(row.grand_total || 0), 0);
    const purchaseTotal = purchase.reduce((sum, row) => sum + Number(row.grand_total || 0), 0);
    const stockValue = items.reduce((sum, row) => sum + Number(row.cost_price || 0), 0);
    return {
      trialBalance: accounts.slice(0, 18).map((row) => ({
        code: row.code,
        name: row.name,
        type: safeText(row.account_type),
        normal: safeText(row.normal_balance),
        debit: safeText(row.normal_balance) === "debit" ? 0 : "",
        credit: safeText(row.normal_balance) === "credit" ? 0 : ""
      })),
      profitLoss: {
        revenue_accounts: byType.revenue || 0,
        expense_accounts: byType.expense || 0,
        sales_total: salesTotal,
        purchase_total: purchaseTotal,
        net_preview: salesTotal - purchaseTotal
      },
      balanceSheet: {
        asset_accounts: byType.asset || 0,
        liability_accounts: byType.liability || 0,
        equity_accounts: byType.equity || 0,
        inventory_cost_basis: stockValue
      },
      inventory: items.slice(0, 20).map((row) => ({
        code: row.code,
        name: row.name,
        type: row.item_type,
        sales_price: row.sales_price,
        cost_price: row.cost_price,
        uom: safeText(row.uom_id)
      }))
    };
  }

  function field(label, node) {
    return D.label({ class: "field" }, [D.span(label), node]);
  }

  function input(name, value, gkey, type) {
    return D.input({ name, value: value == null ? "" : value, type: type || "text", gkey: gkey || "input" });
  }

  function select(name, value, options, gkey) {
    return D.select({ name, value: value == null ? "" : value, gkey: gkey || "input" }, (options || []).map((opt) => {
      const pair = Array.isArray(opt) ? opt : [opt, opt];
      return D.option({ value: pair[0], selected: String(pair[0]) === String(value == null ? "" : value) }, pair[1]);
    }));
  }

  function statusBlock(db) {
    return D.div({ class: "row" }, [
      D.span({ class: "health-dot " + (db.health && db.health.status === "ok" ? "ok" : "") }),
      D.span({ class: "muted" }, db.health ? `upstream ${db.health.upstream_status || "-"} | ${db.health.service}` : "health not loaded"),
      db.error ? D.span({ class: "badge bad" }, "partial load") : D.span({ class: "badge ok" }, db.status || "ready")
    ]);
  }

  function Dashboard(db) {
    const sales = db.rows.sales_invoice_hd || [];
    const purchases = db.rows.purch_invoice_hd || [];
    const salesTotal = sales.reduce((sum, row) => sum + Number(row.grand_total || 0), 0);
    const purchaseTotal = purchases.reduce((sum, row) => sum + Number(row.grand_total || 0), 0);
    const bars = [
      ["Sales", salesTotal],
      ["Purchases", purchaseTotal],
      ["Inventory cost", db.reports.balanceSheet.inventory_cost_basis || 0]
    ];
    const max = Math.max.apply(null, bars.map((item) => item[1]).concat([1]));
    return D.div({ class: "grid" }, [
      D.div({ class: "stat-grid" }, [
        Kit.Stat("الحسابات", (db.rows.fin_accounts || []).length, "teal"),
        Kit.Stat("الأصناف", (db.rows.inv_items || []).length, "blue"),
        Kit.Stat("المخازن", (db.rows.inv_warehouses || []).length, "violet"),
        Kit.Stat("فواتير بيع", sales.length, "amber"),
        Kit.Stat("فواتير شراء", purchases.length, "rose")
      ]),
      D.div({ class: "grid cols2" }, [
        Kit.Panel("تشغيل الخدمة", D.div({ class: "stack" }, [
          statusBlock(db),
          D.div({ class: "log" }, JSON.stringify(db.health || {}, null, 2))
        ]), [D.a({ class: "btn", href: "/health", target: "_blank" }, "Health JSON")]),
        Kit.Panel("مؤشرات مالية مباشرة", D.div({ class: "bar-list" }, bars.map((item) => D.div({ class: "bar-row" }, [
          D.strong(item[0]),
          D.div({ class: "bar" }, D.i({ style: `width:${Math.max(4, Math.round(item[1] / max * 100))}%` })),
          D.span({ class: "code" }, money(item[1]))
        ]))), [])
      ]),
      Kit.Panel("آخر فواتير البيع", invoiceTable(sales.slice(0, 8)), [D.button({ class: "btn", "data-route": "sales", gkey: "route" }, "فتح البيع")])
    ]);
  }

  function invoiceTable(rows) {
    return Kit.Table([
      { key: "doc_no", label: "رقم" },
      { key: "doc_date", label: "التاريخ" },
      { key: "entity_id", label: "الطرف", render: (row) => safeText(row.entity_id) },
      { key: "status", label: "الحالة" },
      { key: "grand_total", label: "الإجمالي", render: (row) => money(row.grand_total) }
    ], rows, "لا توجد فواتير");
  }

  function Masters(db) {
    const config = MASTER_TABLES[db.masterTab];
    const rows = db.rows[config.table] || [];
    const columns = config.fields.slice(0, 6).map((key) => ({ key, label: labelFor(db, config.table, key), render: (row) => safeText(row[key]) }));
    columns.unshift({ key: "ID", label: "ID", render: (row) => rowId(row) });
    return D.div({ class: "grid cols2" }, [
      Kit.Panel("محرك CRUD العام", D.div([
        D.div({ class: "tabs" }, Object.keys(MASTER_TABLES).map((key) => D.button({ class: db.masterTab === key ? "active" : "", "data-tab": key, gkey: "masterTab" }, MASTER_TABLES[key].title))),
        Kit.Table(columns, rows, "لا توجد بيانات")
      ]), [D.button({ class: "btn", gkey: "refresh" }, "تحديث")]),
      Kit.Panel(db.masterEditId ? "تعديل سجل" : "إضافة سجل", D.div({ class: "stack" }, [
        D.div({ class: "form-grid" }, config.fields.map((key) => field(labelFor(db, config.table, key), masterInput(db, key, db.masterForm[key])))),
        D.div({ class: "row" }, [
          D.button({ class: "btn primary", gkey: "saveMaster" }, "حفظ عبر MasStore"),
          D.button({ class: "btn", gkey: "resetMaster" }, "سجل جديد"),
          D.span({ class: "muted" }, config.table)
        ]),
        D.div({ class: "log" }, JSON.stringify({ table: config.table, row: db.masterForm }, null, 2))
      ]), [])
    ]);
  }

  function labelFor(db, table, key) {
    const schema = db.schemas[table];
    const col = schema && Array.isArray(schema.columns) ? schema.columns.find((item) => item.name === key) : null;
    return (col && (col.trans_name || col.name)) || key;
  }

  function masterInput(db, key, value) {
    if (key === "account_type") return select(key, value, ["asset", "liability", "equity", "revenue", "expense"], "masterInput");
    if (key === "report_type") return select(key, value, ["balance_sheet", "income_statement"], "masterInput");
    if (key === "normal_balance") return select(key, value, ["debit", "credit"], "masterInput");
    if (key === "item_type") return select(key, value, ["stock", "service", "non_stock"], "masterInput");
    if (key === "warehouse_kind") return select(key, value, ["general", "sales", "purchase", "returns"], "masterInput");
    if (key.indexOf("is_") === 0) return D.input({ type: "checkbox", name: key, checked: !!value, gkey: "masterInput" });
    if (key.indexOf("price") >= 0 || key === "uom_id" || key === "branch_id") return input(key, value, "masterInput", "number");
    return input(key, value, "masterInput");
  }

  function DocumentPage(db, kind) {
    const isPurchase = kind === "purchase";
    const doc = db.doc[kind];
    const list = db.rows[doc.headTable] || [];
    const profile = doc.profile || db.profiles[kind] || {};
    const collection = firstCollection(profile);
    const detailTable = (collection && collection.table) || (isPurchase ? "purch_invoice_dtl" : "sales_invoice_dtl");
    const title = isPurchase ? "فاتورة شراء" : "فاتورة بيع";
    return D.div({ class: "doc-layout" }, [
      Kit.Panel(title, D.div({ class: "stack" }, [
        D.div({ class: "form-grid" }, [
          field("رقم المستند", input("doc_no", doc.header.doc_no || (doc.preview && doc.preview.doc_no) || "", "docHeader")),
          field("تاريخ المستند", input("doc_date", doc.header.doc_date, "docHeader", "date")),
          field(isPurchase ? "المورد" : "العميل", input("entity_id", doc.header.entity_id, "docHeader", "number")),
          field("المخزن", select("warehouse_id", doc.header.warehouse_id, warehouseOptions(db), "docHeader")),
          field("العملة", input("currency_id", doc.header.currency_id, "docHeader", "number")),
          field("تاريخ الاستحقاق", input("due_date", doc.header.due_date, "docHeader", "date")),
          field("مرجع خارجي", input("ref_no", doc.header.ref_no || "", "docHeader")),
          field("ملاحظات", input("remarks", doc.header.remarks || "", "docHeader"))
        ]),
        D.div({ class: "line-editor" }, doc.lines.map((line, index) => lineEditor(db, kind, line, index))),
        D.div({ class: "row" }, [
          D.button({ class: "btn", "data-kind": kind, gkey: "addLine" }, "إضافة بند"),
          D.button({ class: "btn primary", "data-kind": kind, "data-detail": detailTable, gkey: "saveDraft" }, doc.saving ? "جار الحفظ..." : "حفظ مسودة"),
          D.button({ class: "btn warn", "data-kind": kind, "data-detail": detailTable, gkey: "finalizeDoc" }, "اعتماد نهائي")
        ]),
        doc.error ? D.div({ class: "badge bad" }, doc.error) : null,
        doc.result ? D.div({ class: "log" }, JSON.stringify(doc.result, null, 2)) : null
      ]), [D.button({ class: "btn", "data-kind": kind, gkey: "loadDocDefaults" }, "Defaults")]),
      D.div({ class: "grid" }, [
        Kit.Panel("إجماليات", totalsView(doc), []),
        Kit.Panel("آخر المستندات", invoiceTable(list.slice(0, 12)), [])
      ])
    ]);
  }

  function warehouseOptions(db) {
    const rows = db.rows.inv_warehouses || [];
    const opts = rows.map((row) => [rowId(row), `${row.code || ""} - ${row.name || ""}`]);
    return opts.length ? opts : [["10", "WH001 - Main Warehouse"]];
  }

  function itemOptions(db) {
    const rows = db.rows.inv_items || [];
    const opts = rows.map((row) => [rowId(row), `${row.code || ""} - ${row.name || ""}`]);
    return [["", "اختر صنف"], ...opts];
  }

  function lineEditor(db, kind, line, index) {
    return D.div({ class: "line-row", "data-kind": kind, "data-index": index }, [
      field("الصنف", select("item_id", line.item_id, itemOptions(db), "lineInput")),
      field("الوحدة", input("uom_id", line.uom_id || "9", "lineInput", "number")),
      field("الكمية", input("qty", line.qty, "lineInput", "number")),
      field("السعر", input("price", line.price, "lineInput", "number")),
      field("خصم", input("discount_value", line.discount_value, "lineInput", "number")),
      D.button({ class: "btn danger", "data-kind": kind, "data-index": index, gkey: "removeLine" }, "×")
    ]);
  }

  function normalizedLines(doc) {
    return (doc.lines || []).map((line, index) => store.normalizeDocLine(Object.assign({}, line, { line_no: index + 1 }))).filter((line) => line.item_id);
  }

  function totalsView(doc) {
    const lines = normalizedLines(doc);
    const subtotal = lines.reduce((sum, line) => sum + Number(line.qty || 0) * Number(line.price || 0), 0);
    const discount = lines.reduce((sum, line) => sum + Number(line.discount_value || 0), 0);
    const tax = lines.reduce((sum, line) => sum + Number(line.tax_value || 0), 0);
    const total = lines.reduce((sum, line) => sum + Number(line.line_total || 0), 0);
    return D.div({ class: "totals" }, [
      D.div([D.span("عدد البنود"), D.strong(lines.length)]),
      D.div([D.span("قبل الخصم"), D.strong(money(subtotal))]),
      D.div([D.span("الخصم"), D.strong(money(discount))]),
      D.div([D.span("الضريبة"), D.strong(money(tax))]),
      D.div([D.span("الإجمالي"), D.strong(money(total))])
    ]);
  }

  function Inventory(db) {
    const rows = db.reports.inventory || [];
    return D.div({ class: "grid cols2" }, [
      Kit.Panel("تقرير حركة المخزون", Kit.Table([
        { key: "code", label: "كود" },
        { key: "name", label: "الصنف" },
        { key: "type", label: "النوع" },
        { key: "cost_price", label: "تكلفة", render: (row) => money(row.cost_price) },
        { key: "sales_price", label: "بيع", render: (row) => money(row.sales_price) },
        { key: "uom", label: "الوحدة" }
      ], rows, "لا توجد أصناف"), [D.button({ class: "btn", gkey: "refresh" }, "تحديث")]),
      Kit.Panel("كارت صنف", D.div({ class: "stack" }, [
        D.div({ class: "muted" }, "يعرض هذا الإصدار بيانات الصنف الأساسية من Quantum. وظيفة الحركة التفصيلية مرتبطة بعقد MasStore.func عندما تتاح دوال المخزون."),
        D.div({ class: "log" }, JSON.stringify((db.rows.inv_items || [])[0] || {}, null, 2))
      ]), [])
    ]);
  }

  function Finance(db) {
    const pl = db.reports.profitLoss || {};
    const bs = db.reports.balanceSheet || {};
    return D.div({ class: "grid" }, [
      D.div({ class: "stat-grid" }, [
        Kit.Stat("حسابات الإيراد", pl.revenue_accounts || 0, "teal"),
        Kit.Stat("حسابات المصروف", pl.expense_accounts || 0, "rose"),
        Kit.Stat("صافي مبدئي", money(pl.net_preview || 0), "blue"),
        Kit.Stat("الأصول", bs.asset_accounts || 0, "violet"),
        Kit.Stat("الخصوم", bs.liability_accounts || 0, "amber")
      ]),
      D.div({ class: "grid cols2" }, [
        Kit.Panel("ميزان مراجعة", Kit.Table([
          { key: "code", label: "كود" },
          { key: "name", label: "حساب" },
          { key: "type", label: "نوع" },
          { key: "normal", label: "طبيعة" },
          { key: "debit", label: "مدين", render: (row) => row.debit === "" ? "" : money(row.debit) },
          { key: "credit", label: "دائن", render: (row) => row.credit === "" ? "" : money(row.credit) }
        ], db.reports.trialBalance, "لا توجد حسابات"), []),
        Kit.Panel("قوائم ختامية", D.div({ class: "stack" }, [
          D.div({ class: "totals" }, [
            D.div([D.span("إجمالي المبيعات"), D.strong(money(pl.sales_total || 0))]),
            D.div([D.span("إجمالي المشتريات"), D.strong(money(pl.purchase_total || 0))]),
            D.div([D.span("مخزون بالتكلفة"), D.strong(money(bs.inventory_cost_basis || 0))])
          ]),
          D.div({ class: "log" }, JSON.stringify({ profit_loss: pl, balance_sheet: bs }, null, 2))
        ]), [])
      ])
    ]);
  }

  function body(db) {
    const page = db.route === "masters" ? Masters(db)
      : db.route === "sales" ? DocumentPage(db, "sales")
      : db.route === "purchase" ? DocumentPage(db, "purchase")
      : db.route === "inventory" ? Inventory(db)
      : db.route === "finance" ? Finance(db)
      : Dashboard(db);
    return Kit.Shell(Object.assign({}, db, { title: ROUTES[db.route] || "MAS ERP" }), page);
  }

  const orders = {
    route: { on: "click", do: (event, ctx) => {
      const route = event.target.closest("[data-route]").dataset.route;
      location.hash = `#/${route}`;
      ctx.set({ route, title: ROUTES[route] || "MAS ERP" });
    }},
    refresh: { on: "click", do: (event, ctx) => refresh(ctx) },
    masterTab: { on: "click", do: (event, ctx) => {
      const tab = event.target.closest("[data-tab]").dataset.tab;
      const cfg = MASTER_TABLES[tab];
      ctx.set({ masterTab: tab, masterEditId: "", masterForm: Object.assign({ code: `MAS-${Date.now().toString(36).slice(-5)}`, name: "" }, cfg.defaults) });
    }},
    masterInput: { on: ["input", "change"], do: (event, ctx) => {
      const form = Object.assign({}, ctx.db.masterForm);
      form[event.target.name] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
      ctx.set({ masterForm: form });
    }},
    resetMaster: { on: "click", do: (event, ctx) => {
      const cfg = MASTER_TABLES[ctx.db.masterTab];
      ctx.set({ masterEditId: "", masterForm: Object.assign({ code: `MAS-${Date.now().toString(36).slice(-5)}`, name: "" }, cfg.defaults) });
    }},
    saveMaster: { on: "click", do: async (event, ctx) => {
      const cfg = MASTER_TABLES[ctx.db.masterTab];
      ctx.set({ loading: true, error: "", status: `saving ${cfg.table}` });
      try {
        await store.save(cfg.table, ctx.db.masterForm);
        await refresh(ctx);
      } catch (error) {
        ctx.set({ loading: false, error: error.message || String(error), status: "save failed" });
      }
    }},
    docHeader: { on: ["input", "change"], do: (event, ctx) => {
      const routeKind = ctx.db.route === "purchase" ? "purchase" : "sales";
      const current = ctx.db.doc[routeKind];
      const header = Object.assign({}, current.header, { [event.target.name]: event.target.value });
      const doc = Object.assign({}, ctx.db.doc, { [routeKind]: Object.assign({}, current, { header, result: null, error: "" }) });
      ctx.set({ doc });
    }},
    lineInput: { on: ["input", "change"], do: (event, ctx) => {
      const row = event.target.closest("[data-kind]");
      const kind = row.dataset.kind;
      const index = Number(row.dataset.index);
      const current = ctx.db.doc[kind];
      const lines = current.lines.slice();
      lines[index] = Object.assign({}, lines[index], { [event.target.name]: event.target.value });
      if (event.target.name === "item_id") {
        const item = (ctx.db.rows.inv_items || []).find((candidate) => String(rowId(candidate)) === String(event.target.value));
        if (item) {
          lines[index].uom_id = idOf(item.uom_id) || lines[index].uom_id || "9";
          lines[index].price = kind === "purchase" ? Number(item.cost_price || 0) : Number(item.sales_price || item.cost_price || 0);
        }
      }
      const doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { lines, result: null, error: "" }) });
      ctx.set({ doc });
    }},
    addLine: { on: "click", do: (event, ctx) => {
      const kind = event.target.closest("[data-kind]").dataset.kind;
      const current = ctx.db.doc[kind];
      const doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { lines: current.lines.concat([store.emptyLine()]) }) });
      ctx.set({ doc });
    }},
    removeLine: { on: "click", do: (event, ctx) => {
      const row = event.target.closest("[data-kind]");
      const kind = row.dataset.kind;
      const index = Number(row.dataset.index);
      const current = ctx.db.doc[kind];
      const lines = current.lines.filter((_, i) => i !== index);
      const doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { lines: lines.length ? lines : [store.emptyLine()] }) });
      ctx.set({ doc });
    }},
    loadDocDefaults: { on: "click", do: async (event, ctx) => loadDocument(ctx, event.target.closest("[data-kind]").dataset.kind) },
    saveDraft: { on: "click", do: async (event, ctx) => saveDocument(ctx, event.target.closest("[data-kind]").dataset.kind, event.target.closest("[data-detail]").dataset.detail, false) },
    finalizeDoc: { on: "click", do: async (event, ctx) => {
      if (!global.confirm("اعتماد المستند سيرسل الترحيل النهائي إلى Quantum. هل تريد المتابعة؟")) return;
      await saveDocument(ctx, event.target.closest("[data-kind]").dataset.kind, event.target.closest("[data-detail]").dataset.detail, true);
    }}
  };

  async function saveDocument(ctx, kind, detailTable, finalize) {
    const current = ctx.db.doc[kind];
    const lines = normalizedLines(current);
    if (!lines.length) {
      const doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { error: "أضف بنداً واحداً على الأقل قبل الحفظ." }) });
      ctx.set({ doc });
      return;
    }
    const subtotal = lines.reduce((sum, line) => sum + Number(line.qty || 0) * Number(line.price || 0), 0);
    const discount = lines.reduce((sum, line) => sum + Number(line.discount_value || 0), 0);
    const tax = lines.reduce((sum, line) => sum + Number(line.tax_value || 0), 0);
    const total = lines.reduce((sum, line) => sum + Number(line.line_total || 0), 0);
    const header = Object.assign({}, current.header, {
      tenant_id: 3,
      branch_id: Number(current.header.branch_id || 1),
      subtotal,
      discount_total: discount,
      tax_total: tax,
      grand_total: total,
      status: finalize ? "finalized" : "draft"
    });
    let doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { saving: true, error: "", result: null }) });
    ctx.set({ doc });
    try {
      const payload = {
        headTable: current.headTable,
        detailTable,
        headerRow: header,
        lineRows: lines,
        session: SESSION
      };
      const result = finalize ? await store.finalizeDocument(payload) : await store.saveDocumentDraft(payload);
      doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { saving: false, result, error: "" }) });
      ctx.set({ doc });
      await refresh(ctx);
    } catch (error) {
      doc = Object.assign({}, ctx.db.doc, { [kind]: Object.assign({}, current, { saving: false, error: error.message || String(error) }) });
      ctx.set({ doc });
    }
  }

  const ui = app(body, state, orders).mount("#app");
  global.masErpV2 = { ui, store };
  global.addEventListener("hashchange", () => ui.set({ route: routeFromHash(), title: ROUTES[routeFromHash()] || "MAS ERP" }));
  refresh(ui);
})(typeof window !== "undefined" ? window : globalThis);
