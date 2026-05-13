;(function (global) {
  "use strict";
  const { D } = global.MAS || {};
  if (!D) return;

  function icon(name) {
    const map = {
      dashboard: "M3 13h8V3H3v10zm10 8h8V3h-8v18zM3 21h8v-6H3v6z",
      items: "M4 7l8-4 8 4-8 4-8-4zm0 3l8 4 8-4v7l-8 4-8-4v-7z",
      docs: "M6 3h9l5 5v13H6V3zm8 1v5h5",
      reports: "M4 19V5h16v14H4zm4-3V9m4 7v-5m4 5V7",
      settings: "M12 8a4 4 0 100 8 4 4 0 000-8z"
    };
    return D.svg({ viewBox: "0 0 24 24", width: 18, height: 18, "aria-hidden": "true" }, [
      D.path({ d: map[name] || map.dashboard, fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "stroke-linejoin": "round" })
    ]);
  }

  function Shell(db, children) {
    const menu = [
      ["dashboard", "لوحة القيادة", "Dashboard", "dashboard"],
      ["masters", "البيانات الأساسية", "Masters", "items"],
      ["sales", "فواتير البيع", "Sales", "docs"],
      ["purchase", "فواتير الشراء", "Purchase", "docs"],
      ["inventory", "تقارير المخزون", "Inventory", "reports"],
      ["finance", "التقارير المالية", "Finance", "reports"]
    ];
    return D.div({ class: "erp-shell" }, [
      D.aside({ class: "erp-side" }, [
        D.div({ class: "brand" }, [D.strong("MAS ERP"), D.span("V2 / Quantum")]),
        D.nav({ class: "menu" }, menu.map((item) => D.button({
          class: db.route === item[0] ? "active" : "",
          gkey: "route",
          "data-route": item[0],
          title: item[2]
        }, [icon(item[3]), D.span(item[1]), D.small(item[2])])))
      ]),
      D.main({ class: "erp-main" }, [
        D.header({ class: "topbar" }, [
          D.div([D.h1(db.title || "MAS ERP"), D.p("واجهة ERP جديدة مبنية بـ MAS Core V2 + MasStore V3 فوق Quantum APIs")]),
          D.div({ class: "top-actions" }, [
            D.button({ class: "btn", gkey: "refresh" }, "تحديث"),
            D.a({ class: "btn", href: "/health", target: "_blank" }, "Health")
          ])
        ]),
        D.section({ class: "workspace" }, children)
      ])
    ]);
  }

  function Stat(label, value, tone) {
    return D.article({ class: "stat " + (tone || "") }, [D.span(label), D.strong(value == null ? "-" : String(value))]);
  }

  function Table(columns, rows, empty) {
    return D.div({ class: "table-wrap" }, [
      D.table([D.thead(D.tr(columns.map((col) => D.th(col.label)))), D.tbody((rows || []).length ? rows.map((row) => D.tr(columns.map((col) => D.td(col.render ? col.render(row) : String(row[col.key] == null ? "" : row[col.key]))))) : D.tr([D.td({ colspan: columns.length, class: "empty" }, empty || "لا توجد بيانات")]))])
    ]);
  }

  function Panel(title, body, actions) {
    return D.section({ class: "panel" }, [
      D.div({ class: "panel-head" }, [D.h2(title), D.div({ class: "row" }, actions || [])]),
      body
    ]);
  }

  global.MasDashboardKit = { Shell, Stat, Table, Panel, icon };
})(typeof window !== "undefined" ? window : globalThis);
