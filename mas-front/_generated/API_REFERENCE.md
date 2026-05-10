# MAS JS V2 — API Reference

## Core API
| Method | Signature | Description |
|--------|-----------|-------------|
| `app` | `app(bodyFn, db, orders)` | Create application instance |
| `component` | `component(name, fn, memo?)` | Register reusable component |
| `module` | `module(name, config)` | Register self-contained module |
| `hook` | `hook(name, fn)` | Subscribe to lifecycle events |
| `router` | `router(app, routes, opts?)` | Create hash/history router |
| `load` | `load(url)` | Lazy-load external script |
| `t` | `t(db, key)` | i18n translation lookup |

## Module Config
```js
module('name', {
  db: {},           // initial state (namespaced)
  persist: [],      // keys auto-saved to localStorage
  orders: {},       // gkey -> handler map
  ui: ($, D) => {}, // render function
  css: '',          // scoped styles (auto-injected)
  fetch: ($) => {}, // auto-called on mount
  memo: false       // skip re-render if props unchanged
})
```

## ctx ($) API
| Method | What |
|--------|------|
| `$.db` | current module state |
| `$.set({k:v})` | merge + re-render |
| `$.push(key, item)` | append to array |
| `$.drop(key, id)` | remove from array |
| `$.patch(key, id, changes)` | update item in array |
| `$.toggle(key)` | flip boolean |
| `$.bind(e)` | auto-bind input by name |
| `$.id(e)` | get data-id from closest parent |
| `$.item(key, e)` | find item by data-id |
| `$.setEnv(k, v)` | set environment variable |

## D (DSL) API
```js
D.div({class:'x'}, [children])  // create element
D.show(condition, vnode)        // conditional render
D.unless(condition, vnode)      // inverse conditional
D.myComponent({props})          // render registered component
D.h('tag', attrs, children)     // explicit tag creation
```

## Lifecycle Hooks
```js
MAS.hook('onRender', ({db, root}) => {})
MAS.hook('onState', ({prev, next}) => {})
MAS.hook('onError', ({error, gkey}) => {})
```
