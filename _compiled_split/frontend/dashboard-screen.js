// ══════════════════════════════════════════════════════
// AI-First Compiled Output
// Module: Frontend | Component: Dashboard
// Generated: 2026-05-09T13:03:24Z
// WARNING: This file is auto-generated. Do not edit.
// The source of truth is the database.
// ══════════════════════════════════════════════════════

MAS.module('dashboard-screen', {
  db: {
    health: [],
    projects: [],
    loading: true
  },

  orders: {
    load: async function(ctx) {
      ctx.db.loading = true;
      ctx.db.health = await API.healthAll();
      ctx.db.projects = await API.listProjects();
      ctx.db.loading = false;
    }
  },

  body: function(ctx) {
    return ["div", { class: "dashboard" },
      ["h1", {}, t("dashboard.title")],
      ["div", { class: "health-grid" },
        ctx.db.health.map(function(s) {
          return ["div", { class: "health-card" }, s.name, " — ", s.status];
        })
      ]
    ];
  },

  style: `
    .dashboard { padding:24px; }
    .health-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:16px; }
    .health-card { background:var(--bg-card); padding:16px; border-radius:8px; }
  `
});