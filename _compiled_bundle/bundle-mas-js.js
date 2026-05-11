// ══════════════════════════════════════════════════════
// AI-First Compiled Output
// Strategy: single-bundle | Target: mas-js
// Generated: 2026-05-09T13:03:24Z
// WARNING: This file is auto-generated. Do not edit.
// The source of truth is the database.
// ══════════════════════════════════════════════════════


// ──────────────────────────────────────────────────
// Global Variables
// ──────────────────────────────────────────────────

const API_VERSION = "1.0";
const APP_NAME = "AI-First Platform";
const MAX_PAGE_SIZE = "100";

// ──────────────────────────────────────────────────
// Shared Functions
// ──────────────────────────────────────────────────


// fn: slugify
//   Convert text to URL-safe slug
function slugify(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// ──────────────────────────────────────────────────
// Design Tokens
// ──────────────────────────────────────────────────

const _DESIGN_TOKENS_CSS = `
:root {
  --bg-card: #1a2332;
  --color-error: #ef4444;
  --color-primary: #3b82f6;
  --color-success: #10b981;
  --radius-md: 10px;
  --space-md: 16px;
}
`;

// ──────────────────────────────────────────────────
// i18n Translations
// ──────────────────────────────────────────────────

const I18N = {
  "ar": {
    "dashboard.title": "لوحة التحكم",
    "login.submit": "دخول",
    "login.title": "تسجيل الدخول"
  },
  "en": {
    "dashboard.title": "Dashboard",
    "login.submit": "Sign In",
    "login.title": "Sign In"
  }
};

// ──────────────────────────────────────────────────
// Module: Frontend | Component: Login Screen
// ──────────────────────────────────────────────────

MAS.module('login-screen', {
  db: {
    email: "",
    password: "",
    error: null,
    loading: false
  },

  orders: {
    submit: async function(ctx) {
      ctx.db.loading = true;
      ctx.db.error = null;
      try {
        var result = await API.login(ctx.db.email, ctx.db.password);
        ctx.navigate("dashboard");
      } catch(e) {
        ctx.db.error = e.message;
      }
      ctx.db.loading = false;
    }
  },

  body: function(ctx) {
    return ["div", { class: "login-screen" },
      ["div", { class: "login-card" },
        ["h1", {}, t("login.title")],
        ctx.db.error ? ["div", { class: "error" }, ctx.db.error] : null,
        ["input", { type: "email", value: ctx.db.email,
                    oninput: function(e) { ctx.db.email = e.target.value; } }],
        ["input", { type: "password", value: ctx.db.password,
                    oninput: function(e) { ctx.db.password = e.target.value; } }],
        ["button", { onclick: function() { ctx.order("submit"); },
                     disabled: ctx.db.loading }, t("login.submit")]
      ]
    ];
  },

  style: `
    .login-screen { display:flex; align-items:center; justify-content:center; min-height:100vh; }
    .login-card { background:var(--bg-card); padding:32px; border-radius:12px; width:400px; }
    .login-card h1 { color:var(--color-primary); margin-bottom:24px; }
    .login-card input { width:100%; padding:12px; margin-bottom:12px; }
    .error { color:var(--color-error); margin-bottom:12px; }
  `
});

// ──────────────────────────────────────────────────
// Module: Frontend | Component: Dashboard
// ──────────────────────────────────────────────────

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