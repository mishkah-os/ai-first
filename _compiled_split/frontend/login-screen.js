// ══════════════════════════════════════════════════════
// AI-First Compiled Output
// Module: Frontend | Component: Login Screen
// Generated: 2026-05-09T13:03:24Z
// WARNING: This file is auto-generated. Do not edit.
// The source of truth is the database.
// ══════════════════════════════════════════════════════

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