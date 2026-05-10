# MAS JS Framework

**A browser-native UI runtime built on three hard constraints: one state, one render path, one source of truth.**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](#license)
[![UMD](https://img.shields.io/badge/delivery-UMD%20%2B%20ESM-green.svg)](#loading)
[![No Build](https://img.shields.io/badge/build%20step-none-brightgreen.svg)](#loading)

---

## What is MAS?

MAS is a JavaScript UI framework that runs directly in the browser — no bundler, no compiler, no build pipeline. Drop a `<script>` tag and you have a reactive application with a virtual DOM, i18n, theming, event delegation, and a component library.

It is not a React alternative. It is a different architectural bet: instead of composing state across components, you keep **all state in one object** and derive the entire UI from it on every render. The framework handles the diffing. You handle the logic.

```
State (db)  →  body(db)  →  VDOM  →  surgical DOM patch
     ↑                                        |
     └──────────── orders (event handlers) ───┘
```

---

## Core Constraints

These are not conventions. They are enforced by the architecture.

| Constraint | What it means |
|---|---|
| **Single state object** | All application data lives in `db`. No component-local state. |
| **Pure render function** | `body(db)` is a pure function. No side effects, no fetch, no mutation. |
| **Centralized handlers** | All mutations happen in `orders`. No inline event logic in the UI. |
| **Delegated events** | One listener at the app root. Handlers are matched by `gkey`. |

---

## Loading

MAS ships as UMD. It runs in the browser without any build step, and on Node.js (V8) for SSR.

```html
<!-- Core: VDOM, DSL, i18n, event delegation, app factory -->
<script src="https://ws.mas.com.eg/lib2/mas.core.js"></script>

<!-- UI: component library + design tokens + Chart.js bridge -->
<script src="https://ws.mas.com.eg/lib2/mas-ui.js"></script>

<!-- Utilities: twcss, storage, network helpers (optional) -->
<script src="https://ws.mas.com.eg/lib2/mas-utils.js"></script>

<!-- Persistence: IndexedDB adapter (optional) -->
<script src="https://ws.mas.com.eg/lib2/mas-indexeddb.js"></script>
```

For ES module projects, use the bridge pattern — see [Module System](#module-system).

---

## Quick Start

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://ws.mas.com.eg/lib2/mas.core.js"></script>
  <script src="https://ws.mas.com.eg/lib2/mas-ui.js"></script>
</head>
<body>
  <div id="app"></div>
  <script>
    const { DSL: D, app } = MAS;

    // 1. All state in one object
    const db = {
      env: { theme: 'light', lang: 'en' },
      count: 0
    };

    // 2. All mutations in one place
    const orders = {
      'onClick:counter.inc': (e, ctx) => ctx.setState(s => ({ ...s, count: s.count + 1 })),
      'onClick:counter.dec': (e, ctx) => ctx.setState(s => ({ ...s, count: s.count - 1 }))
    };

    // 3. Pure render function — no side effects
    const body = (db) => D.Div({ attrs: { class: 'p-8 space-y-4' } }, [
      D.H1({ attrs: { class: 'text-2xl font-bold' } }, [`Count: ${db.count}`]),
      D.Div({ attrs: { class: 'flex gap-2' } }, [
        D.Button({ attrs: { gkey: 'counter.dec', class: 'px-4 py-2 bg-slate-200 rounded' } }, ['−']),
        D.Button({ attrs: { gkey: 'counter.inc', class: 'px-4 py-2 bg-blue-600 text-white rounded' } }, ['+'])
      ])
    ]);

    app.setBody(body);
    app.create(db, orders).mount('#app');
  </script>
</body>
</html>
```

---

## Architecture

### State

The `db` object is the single source of truth. Every piece of data the UI needs — user session, language, theme, fetched records, form values — lives here.

```javascript
const db = {
  env: { lang: 'en', theme: 'light' },
  i18n: {
    dict: {
      title: { en: 'Dashboard', ar: 'لوحة التحكم' },
      save:  { en: 'Save',      ar: 'حفظ' }
    }
  },
  user: { name: 'Guest', loggedIn: false },
  data: {}
};
```

Distributed state (multiple `useState` calls, component-local stores) is not the MAS pattern. If two components need the same data, it belongs in `db`.

### Render Function

`body(db)` takes the current state and returns a virtual DOM tree. It must be pure.

```javascript
const t = (db, key) => db.i18n?.dict?.[key]?.[db.env.lang] || key;

const body = (db) => D.Div({ attrs: { class: 'p-4' } }, [
  D.H1({}, [t(db, 'title')]),
  D.Button({ attrs: { gkey: 'save' } }, [t(db, 'save')])
]);
```

The framework diffs the returned VDOM against the previous render and applies only the changed nodes to the DOM.

### Orders

`orders` is a flat object mapping event patterns to handler functions. This is the only place state mutations happen.

```javascript
const orders = {
  // Pattern: 'onClick:<gkey>'
  'onClick:save': (e, ctx) => {
    const state = ctx.getState();
    console.log('saving', state.data);
  },

  // Pattern: 'onClick:<gkey>' with delegated target reading
  'onClick:item.select': (e, ctx) => {
    const node = e.target.closest('[data-id]');
    if (!node) return;
    ctx.setState(s => ({ ...s, selectedId: node.dataset.id }));
  }
};
```

Handler signature is always `(event, ctx)`. Read state with `ctx.getState()`, write with `ctx.setState()`.

### DSL

The DSL (`MAS.DSL`) is a typed element factory. Every HTML element has a corresponding DSL function.

```javascript
const { DSL: D } = MAS;

// D.<Tag>({ attrs: {}, events: {} }, children)
D.Div({ attrs: { class: 'card' } }, [
  D.H2({}, ['Title']),
  D.P({ attrs: { class: 'text-sm' } }, ['Body text']),
  D.Button({ attrs: { gkey: 'action.confirm' } }, ['Confirm'])
])
```

Elements are grouped by category:

| Namespace | Elements |
|---|---|
| `D.*` | `Div`, `Span`, `P`, `H1`–`H6`, `Button`, `A`, `Ul`, `Li`, `Table`, ... |
| `D.Forms.*` | `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Form` |
| `D.Media.*` | `Image`, `Video`, `Audio`, `Canvas`, `Svg` |
| `D.Embedded.*` | `Canvas`, `Iframe` |

### Event System

MAS uses a single delegated listener at the app root. Buttons and interactive elements declare their intent via `gkey`:

```html
<!-- In the VDOM -->
<button gkey="theme.toggle">Toggle Theme</button>
```

```javascript
// In orders
const orders = {
  'onClick:theme.toggle': (e, ctx) => {
    const next = ctx.getState().env.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    ctx.setState(s => ({ ...s, env: { ...s.env, theme: next } }));
  }
};
```

**Rules:**
- Write `gkey="action.name"` — never include the event name inside `gkey`
- Use `onClick:` prefix in orders for click handlers
- Use `e.target.closest('[data-x]')` to read data attributes from delegated events

---

## i18n

Translation is built into the state model. No external library needed.

```javascript
const db = {
  env: { lang: 'ar' },
  i18n: {
    dict: {
      greeting: { en: 'Hello', ar: 'مرحباً' },
      save:     { en: 'Save',  ar: 'حفظ'    }
    }
  }
};

// Translation helper — pure function, no magic
const t = (db, key) => db.i18n?.dict?.[key]?.[db.env.lang] || key;

// Switch language
ctx.setState(s => ({ ...s, env: { ...s.env, lang: 'ar' } }));
document.documentElement.setAttribute('lang', 'ar');
document.documentElement.setAttribute('dir', 'rtl');
```

RTL/LTR is handled by setting `dir` on `<html>`. MAS does not impose a layout system — use CSS variables and Tailwind utilities.

---

## Theming

Themes are CSS variable sets. MAS manages the `data-theme` attribute; you define the variables.

```css
:root {
  --background: #ffffff;
  --foreground: #0f172a;
  --card: #f8fafc;
  --border: #e2e8f0;
  --primary: #2563eb;
  --primary-foreground: #ffffff;
  --muted-foreground: #64748b;
}

[data-theme="dark"] {
  --background: #0f172a;
  --foreground: #f8fafc;
  --card: #1e293b;
  --border: #334155;
  --primary: #60a5fa;
  --primary-foreground: #0f172a;
  --muted-foreground: #94a3b8;
}
```

Toggle:

```javascript
'onClick:theme.toggle': (e, ctx) => {
  const next = ctx.getState().env.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  ctx.setState(s => ({ ...s, env: { ...s.env, theme: next } }));
}
```

---

## UI Component Library

`mas-ui.js` ships a production-ready component library built on the same DSL. Components use CSS variables from your theme automatically.

```javascript
const { UI } = MAS;

// Available components
UI.Button({ variant: 'solid', size: 'md' }, ['Save'])
UI.Card({ title: 'Revenue', description: 'This month' }, [content])
UI.Modal({ open: db.showModal, title: 'Confirm' }, [body])
UI.Drawer({ open: db.drawerOpen, side: 'right' }, [content])
UI.Tabs({ items: tabs, active: db.activeTab })
UI.Badge({ variant: 'ghost' }, ['New'])
UI.Toast({ message: 'Saved', type: 'success' })
UI.ThemeSwitcher({ theme: db.env.theme })
UI.LangSwitcher({ lang: db.env.lang })
UI.Numpad({ value: db.amount })
```

For quick prototypes, `UI.ThemeSwitcher` and `UI.LangSwitcher` handle the toggle boilerplate so you don't have to.

---

## State Management

### Basic update

```javascript
ctx.setState(s => ({ ...s, count: s.count + 1 }));
```

### Batching multiple updates

```javascript
ctx.batch(ctx => {
  ctx.setState(s => ({ ...s, loading: true }));
  ctx.setState(s => ({ ...s, data: newData }));
});
// One render fires after the batch
```

### Manual flush (advanced)

```javascript
ctx.flush({
  keepScroll: ['#list'],   // preserve scroll position on these selectors
  except: ['#chart'],      // skip diffing these nodes
  buildOnly: ['#sidebar']  // rebuild only these subtrees
});
```

### Freeze / unfreeze

```javascript
ctx.freeze();
// ... multiple setState calls
ctx.unfreeze(); // triggers one render
```

`setState()` is reactive by default — it schedules a render automatically. `freeze()` / `batch()` / `flush()` are for cases where you need explicit control.

---

## Module System

For larger apps, split into ES modules. MAS globals are loaded as classic `<script>` tags; a bridge proxy resolves them at access time.

```javascript
// src/core/mas.js — bridge (required for ES module projects)
const get = () => window.MAS || window.Mishkah;

export const D   = new Proxy({}, { get: (_, p) => get()?.DSL?.[p] });
export const app = new Proxy({}, { get: (_, p) => get()?.app?.[p] });
export const UI  = new Proxy({}, { get: (_, p) => get()?.UI?.[p] });
```

Recommended folder structure:

```
src/
├── core/mas.js              ← bridge
├── features/
│   └── <name>/
│       ├── ui.js            ← pure render functions
│       ├── logic.js         ← pure business logic, API calls
│       └── orders.js        ← event handlers
└── app.js                   ← bootstrapper: merge db + orders, mount
```

Feature contracts:

| File | Rule |
|---|---|
| `ui.js` | Pure — no side effects, no fetch, no state mutation |
| `logic.js` | No DSL imports — data only |
| `orders.js` | Uses `ctx.getState()` / `ctx.setState()` only |

State slices by feature:

```javascript
const db = {
  env: { lang: 'en', theme: 'light' },
  pricing:   { plans: [], billingCycle: 'monthly' },
  subscribe: { form: {}, step: 'idle', errors: {} }
};
```

Each feature's orders update only its own slice.

---

## Ecosystem

| Package | Purpose |
|---|---|
| `mas.core.js` | VDOM, DSL, i18n, event delegation, app factory |
| `mas-ui.js` | Component library, design tokens, Chart.js bridge |
| `mas-utils.js` | `twcss`, storage, network helpers |
| `mas-indexeddb.js` | Local persistence adapter |
| `mas.store.js` | SQL-like state management for complex apps |
| `mas-rest.js` | REST client with MAS state integration |
| `mas-crud.js` | CRUD operations with schema validation |
| `mas-schema.js` | Schema-driven UI generation |
| `mas-erd.js` | Entity-relationship diagram renderer |
| `mas.pwa.js` | PWA / offline support |
| `mas.pages.js` | Client-side routing |
| `mas-plotly.js` | Plotly integration |
| `mas-ui-codemirror.js` | CodeMirror integration |
| `mas-dashboard-kit.js` | Dashboard layout primitives |
| `mobile-kit.js` | Mobile-first UI kit |

**Framework adapters** (for gradual migration or hybrid use):

`mas-react.js` · `mas-vue.js` · `mas-svelte.js` · `mas-angular.js` · `mas-solid.js` · `mas-alpine.js`

---

## Governance Layer

MAS ships with a three-part runtime governance system.

### Guardian

Prevents invalid or unsafe VDOM nodes before they reach the DOM. Blocks dangerous tags, enforces URL scheme allowlists, and validates structural rules.

```javascript
MAS.Guardian.setConfig({
  denyTags: { script: 1 },
  allowedUrlSchemes: ['http:', 'https:', 'mailto:']
});
```

### Auditor

Observes runtime behavior and grades component quality on a 14-point scale (`-7` to `+7`). Logs performance metrics, accessibility violations, and architectural deviations.

```javascript
MAS.Auditor.grade('+2', 'IconButton', 'aria-label present');
MAS.Auditor.grade('-7', 'ArticleRenderer', 'innerHTML injection detected');
```

### DevTools

Analyzes Auditor logs and issues component verdicts. Components with consistently high scores are flagged as exemplars; those with low scores are flagged for mandatory review.

```javascript
MAS.Judgment.configure({
  thresholds: { heavenScore: +40, hellScore: -50 },
  gates: { maxSevere: 0 }
});
MAS.Snapshot.print(); // prints component health report
```

---

## Seven Architectural Pillars

The framework is designed around seven constraints that, taken together, make applications predictable and maintainable at scale.

1. **Single source of truth** — `db` is the only place state lives
2. **Constrained DSL** — structure and behavior are separated by the language itself
3. **Functional atom classification** — elements are typed building blocks, not raw tags
4. **Composable component library** — `mas-ui.js` provides production-ready components
5. **Integrated global environment** — i18n, theming, and RTL are first-class, not plugins
6. **Standardized utilities** — one toolkit for storage, networking, and formatting
7. **Reactive by default, explicit control on demand** — `setState` triggers renders; `freeze`/`flush` give surgical control

---

## SSR

Because MAS is UMD and runs on V8, it works in Node.js for server-side rendering without modification.

---

## License

MIT — see [LICENSE](./LICENSE).

---

## Links

- [Quick Start Guide](./QUICK-START.md)
- [Module System](./mas-module-system.md)
- [UI Components](../../lib/Mas-ui.md)
- [Store](../../store/README.md)
- [REST Client](../../lib/Mas-rest.md)
