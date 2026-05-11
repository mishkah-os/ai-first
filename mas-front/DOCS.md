# MAS Framework V2 — Complete Documentation

## What is MAS?
A **39KB full-stack frontend framework** (JS 34KB + CSS 6KB). Includes: VDOM, modules, router, SSR, hydration, lazy loading, event delegation, head management, design tokens, Chart.js bridge. Zero build step. Zero dependencies.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│  Backend (C++/PostgreSQL)                    │
│  Sends flat, pre-translated JSON             │
└──────────┬───────────────────────────────────┘
           │  GET /api/products?lang=ar
           ▼
┌──────────────────────────────────────────────┐
│  MAS Frontend                                │
│                                              │
│  module('todo', {                            │
│    db:     { items:[], input:'' },            │
│    orders: { add: do(e,$){ $.push(...) } },   │
│    ui:     ($, D) => D.div([...]),            │
│    css:    '.todo {...}'                      │
│  })                                          │
│                                              │
│  body(db) → D.div([D.todo(), D.counter()])   │
│                  ↓                           │
│              VDOM → DOM                      │
└──────────────────────────────────────────────┘
```

---

## Module — The Core Unit

Every feature is a **module**: a self-contained capsule with its own state, logic, view, and styles.

```js
MAS.module('todo', {
  db: { items: [], input: '' },

  orders: {
    add: { on: 'click', do(e, $) {
      $.push('items', { id: Date.now(), name: $.db.input })
      $.set({ input: '' })
    }},
    del:    { on: 'click', do(e, $) { $.drop('items', $.id(e)) }},
    toggle: { on: 'click', do(e, $) {
      const item = $.db.items.find(i => i.id === $.id(e))
      $.patch('items', $.id(e), { done: !item.done })
    }},
    input:  { on: 'input', do(e, $) { $.set({ input: e.target.value }) }}
  },

  ui: ($, D) =>
    D.div([
      D.input({ gkey: 'input', value: $.db.input }),   // gkey → 'todo.input'
      D.button({ gkey: 'add' }, '+'),                   // gkey → 'todo.add'
      D.ul($.db.items.map(i =>
        D.li({ key: i.id, 'data-id': i.id }, [
          D.span({ gkey: 'toggle' }, i.name),
          D.button({ gkey: 'del' }, '✕')
        ])
      ))
    ]),

  css: `.mod-todo { padding: 1rem; }`,

  // Optional: auto-fetch data on mount
  fetch: async ($) => {
    const res = await fetch('/api/todos')
    $.set({ items: await res.json(), loading: false })
  }
})
```

### Module Rules:
- **Name must be unique.** Duplicate names trigger a warning.
- **gkeys auto-prefix** with module name: `gkey: 'add'` → `gkey: 'todo.add'`
- **D is module-scoped** — auto-prefixes gkeys in the module's UI
- **`fetch`** runs automatically on `mount()` if defined

---

## $ — Module Context

Passed to both `orders` handlers and `ui` function.

| Property/Method | Description | Example |
|----------------|-------------|---------|
| `$.db` | Module's own state | `$.db.items` |
| `$.set({k:v})` | Update module state (auto-namespaced) | `$.set({input: ''})` |
| `$.push(key, item)` | Add item to array | `$.push('items', newItem)` |
| `$.drop(key, id)` | Remove item by id | `$.drop('items', $.id(e))` |
| `$.patch(key, id, changes)` | Update item by id | `$.patch('items', 5, {done:true})` |
| `$.toggle(key)` | Flip boolean | `$.toggle('expanded')` |
| `$.id(e)` | Extract `data-id` from event target | `$.id(e)` → `42` |
| `$.env` | Global env `{lang, theme}` | `$.env.lang` |
| `$.route` | Current route `{name, params, query}` | `$.route.params.id` |
| `$.root` | Full app state (read-only) | `$.root.counter.value` |
| `$.setRoot({k:v})` | Update global state | `$.setRoot({env:{...}})` |

### Before (ugly) vs After (clean):
```diff
- // Before: 3 lines of boilerplate
- const id = +e.target.closest('[data-id]').dataset.id
- ctx.set({ todo: { ...ctx.db.todo, items: ctx.db.todo.items.filter(i => i.id !== id) }})

+ // After: 1 line
+ $.drop('items', $.id(e))
```

---

## DSL — `D.tag(attrs?, children?)`

Every HTML/SVG element is a function call. No JSX. No templates.

```js
D.div()                              // <div></div>
D.h1('Hello')                        // <h1>Hello</h1>
D.div({class:'box'}, [D.p('text')])  // <div class="box"><p>text</p></div>
D.input({gkey:'name', value: v})     // <input gkey="name" value="...">
```

### Special Props

| Prop | Purpose | Example |
|------|---------|---------|
| `gkey` | Event target (auto-prefixed in modules) | `{gkey:'save'}` |
| `key` | Keyed list diffing | `{key: item.id}` |
| `_html` | Raw HTML injection | `{_html:'<b>bold</b>'}` |
| `_bridge` | External lib bridge | `{_bridge: el => {...}}` |
| `value` | Input value (cursor-safe) | `{value: db.input}` |

### Auto-Head Elements
`D.title()`, `D.meta()`, `D.link()`, `D.base()` automatically go to `<head>`.

---

## App & Mount

```js
const myApp = MAS.app(bodyFn, initialDb, rootOrders).mount('#app')
```

- `bodyFn(db)` — pure function, returns VDOM
- `initialDb` — global state: `{ env: {lang, theme}, ... }`
- `rootOrders` — global event handlers (non-module)

---

## Router

```js
MAS.router(myApp, {
  '/':              'home',
  '/products':      'products',
  '/products/:id':  'detail',
  '*':              'notFound'
}, {
  mode: 'hash',     // 'hash' (default) or 'history'
  guard: (route, state) => state.auth || route.name === 'login',
  beforeEach: (from, to, state) => { /* return false to cancel */ },
  afterEach: (from, to) => { window.scrollTo(0, 0) }
}).start()

MAS.go('/products/42')

// In module UI:
if ($.route.name === 'detail') { /* show detail view */ }
// $.route.params.id === '42'
```

---

## SSR + Hydration

### Server (Node.js):
```js
const MAS = require('./mas.core.js')
const html = MAS.renderToString(bodyFn(db))
const head = MAS.renderHeadToString(db)
// Send full HTML page to client
```

### Client (hydrate instead of mount):
```js
MAS.app(body, db, orders).hydrate('#app')
// ↑ No re-render! Just attaches events to existing DOM
```

---

## Bridge — External Libraries

```js
D.canvas({ _bridge: (el) => {
  if (!el._chart) el._chart = new Chart(el, config)
  else { el._chart.data = newData; el._chart.update() }
  return () => el._chart.destroy()  // cleanup on unmount
}})
```

---

## Lazy Modules

```js
MAS.lazy('charts', '/modules/charts.js')
// First D.charts() → loads script → shows ⏳ → renders module
```

---

## Data Fetching

```js
module('products', {
  db: { items: [], loading: true, error: null },
  fetch: async ($) => {
    try {
      const res = await fetch('/api/products?lang=' + $.env.lang)
      $.set({ items: await res.json(), loading: false })
    } catch(err) {
      $.set({ error: err.message, loading: false })
    }
  },
  orders: {},
  ui: ($, D) =>
    $.db.loading ? D.p('Loading...') :
    $.db.error ? D.p('Error: ' + $.db.error) :
    D.ul($.db.items.map(i => D.li({key:i.id}, i.name)))
})
```

---

## Design Tokens (`mas.tokens.css`)

Works **with** Tailwind. Tokens handle theming.

### Key Variables
```css
--mas-bg, --mas-bg-soft, --mas-bg-elevated
--mas-text, --mas-text-soft, --mas-text-muted
--mas-primary, --mas-secondary, --mas-accent
--mas-success, --mas-warning, --mas-danger
--mas-border, --mas-ring, --mas-radius
--mas-shadow, --mas-font, --mas-font-ar
```

### Classes: `.mas-card`, `.mas-btn`, `.mas-btn-primary`, `.mas-input`, `.mas-badge`

Dark mode auto-switches via `data-theme="dark"` (set by `db.env.theme`).

---

## Hooks

```js
MAS.hook('onRender', ({db, root}) => { })
MAS.hook('onState',  ({prev, next}) => { })
MAS.hook('onError',  ({type, error, gkey}) => { })
```

---

## Priority Scheduling

```js
ctx.set({ input: e.target.value })                    // urgent (rAF)
ctx.set({ analytics: data }, { priority: 'idle' })    // idle (rIC)
```

---

## File Structure Convention

```
app/
  modules/
    todo/mod.js        ← module capsule
    counter/mod.js
    products/mod.js
  main.js              ← assembler
  index.html           ← loads mas.core.js + mas.tokens.css + main.js
```

---

## Data Flow Rule

```
Backend → flat, pre-translated JSON → $.db → UI renders
Frontend NEVER does JOIN, translation lookup, or data transformation
```
