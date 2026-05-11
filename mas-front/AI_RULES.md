# MAS Framework — AI Quick Start
# Give this file to any AI to build any frontend app.

## Module Protocol
```
app/
  modules/
    counter/mod.js    ← self-contained module
    todo/mod.js       ← self-contained module
  main.js             ← assembler
```

## mod.js — Module Shape
```js
MAS.module('todo', {
  db: { items: [], input: '', loading: false },

  // FETCH — auto on mount (optional)
  fetch: async ($) => {
    const res = await fetch('/api/todos')
    $.set({ items: await res.json(), loading: false })
  },

  // ORDERS — logic ($ = module context, gkeys auto-prefixed)
  orders: {
    add:    { on: 'click', do(e, $) {
      const t = $.db.input.trim(); if (!t) return
      $.push('items', { id: Date.now(), name: t })
      $.set({ input: '' })
    }},
    del:    { on: 'click', do(e, $) { $.drop('items', $.id(e)) }},
    toggle: { on: 'click', do(e, $) {
      const i = $.db.items.find(x => x.id === $.id(e))
      $.patch('items', $.id(e), { done: !i.done })
    }},
    input:  { on: 'input', do(e, $) { $.set({ input: e.target.value }) }}
  },

  // UI — view ($ = module context, D auto-prefixes gkeys)
  ui: ($, D) =>
    D.div([
      D.input({ gkey: 'input', class: 'mas-input', value: $.db.input }),
      D.button({ gkey: 'add', class: 'mas-btn mas-btn-primary' }, '+'),
      D.ul($.db.items.map(i =>
        D.li({ key: i.id, 'data-id': i.id }, [
          D.span({ gkey: 'toggle' }, i.name),
          D.button({ gkey: 'del' }, '✕')
        ])
      ))
    ]),

  css: `.todo { padding: 1rem; }`
})
```

## $ — Module Context
```
$.db              module's own state
$.set({k:v})      update module state
$.push(key, item) add to array
$.drop(key, id)   remove from array by id
$.patch(key, id, {changes})  update item in array
$.toggle(key)     flip boolean
$.id(e)           extract data-id from event target
$.env             {lang, theme}
$.route           {name, params, query}
$.root            full app state (read-only)
$.setRoot({k:v})  update global state
```

## main.js — Assembler
```js
import './modules/counter/mod.js'
import './modules/todo/mod.js'

const body = (db) => D.div([
  D.counter(),    // ← auto from module
  D.todo()        // ← auto from module
])

const myApp = MAS.app(body, { env: {lang:'ar', theme:'dark'} }, {
  lang:  { on:'click', do(e,ctx){ ctx.set({env:{...ctx.db.env, lang: ctx.db.env.lang==='ar'?'en':'ar'}}) }},
  theme: { on:'click', do(e,ctx){ ctx.set({env:{...ctx.db.env, theme: ctx.db.env.theme==='dark'?'light':'dark'}}) }},
  nav:   { on:'click', do(e,ctx){ e.preventDefault(); MAS.go(e.target.closest('[data-href]').dataset.href) }}
}).mount('#app')

MAS.router(myApp, {'/':'home', '/about':'about', '*':'home'}, {
  afterEach: () => window.scrollTo(0,0)
}).start()
```

## API Reference
```
D.tag(attrs?, children?)              → vnode
D.tag({gkey:'x'}, [...])             → event-wired (auto-prefixed in modules)
D.tag({key:id}, [...])                → keyed list item
D.tag({_html:'<b>x</b>'})            → raw HTML
D.tag({_bridge: el=>...})            → Chart.js / Canvas
D.title/meta/link()                   → auto <head>

module(name, {db,orders,ui,css,fetch}) → register module
component(name, fn, memo?)             → register component
lazy(name, url)                        → lazy module

app(body, db, orders).mount(sel)       → mount
app(body, db, orders).hydrate(sel)     → SSR hydration

router(app, routes, opts).start()
  opts: {mode, guard, beforeEach, afterEach}
go(path)                               → navigate

hook('onRender'|'onState'|'onError', fn)
load(url) / loaded(url)                → lazy script
renderToString(vnode)                  → SSR
```

## Orders Format
```js
{ gkey: { on: 'click', do(e, $) { $.set({...}) } } }
{ gkey: { on: ['input','keydown'], do(e, $) {...} } }
{ gkey: handlerFn }   // shorthand = click
```

## Router
```js
MAS.router(app, {'/':name, '/x/:id':name, '*':name}, {
  guard: (route, state) => state.auth || route.name==='login',
  beforeEach: (from, to, state) => { /* return false to cancel */ },
  afterEach: (from, to) => { window.scrollTo(0,0) }
}).start()
// $.route.name, $.route.params.id, $.route.query.page
```

## Bridge
```js
D.canvas({ _bridge: (el) => {
  if (!el._chart) el._chart = new Chart(el, config)
  else { el._chart.data = d; el._chart.update() }
  return () => el._chart.destroy()
}})
```

## Lazy Module
```js
MAS.lazy('charts', '/modules/charts.js')
// First D.charts() → loads script → ⏳ → renders
```

## Data Flow
```
Backend → flat JSON → $.db.data → UI renders
Frontend NEVER does JOIN or transform
```
