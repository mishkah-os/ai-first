# MAS V2 — AI Quick Start

## 1. Setup
```html
<script src="mas.core.v2.js"></script>
<script>const { D, app, component, hook } = MAS</script>
```

## 2. Build UI — `D.tag(attrs?, children?)`
```js
D.div({class:'box'}, [D.h1('Title'), D.p('text')])
D.input({gkey:'name', type:'text', value: db.name})
D.button({gkey:'save'}, 'Save')
D.title('Page Title')           // → auto <head>
D.meta({name:'desc',content:'x'}) // → auto <head>
```

## 3. Orders — Wire events to gkey
```js
// Each key = gkey attribute on the element
// on: string or array of event names
// do: handler function(event, ctx)

const orders = {
  save:   { on: 'click', do: handleSave },
  name:   { on: ['input','focus'], do: handleName },
  form:   { on: 'submit', do: handleForm },
  delete: handleDelete  // shorthand = click
}

function handleSave(e, ctx) {
  ctx.set({ saved: true })
}
function handleName(e, ctx) {
  ctx.set({ name: e.target.value })
}
function handleForm(e, ctx) {
  e.preventDefault()
  // ...
}
function handleDelete(e, ctx) {
  const id = e.target.closest('[data-id]').dataset.id
  ctx.set({ items: ctx.db.items.filter(i => i.id !== id) })
}
```

## 4. State — Plain object, merge with `ctx.set()`
```js
const db = {
  env: { lang: 'ar', theme: 'dark' },
  name: '',
  items: [],
  loading: false
}
```

## 5. Body — Pure function `(db) => vnode`
```js
const body = (db) =>
  D.div({class:'app'}, [
    D.h1(db.name || 'Untitled'),
    D.input({gkey:'name', value: db.name}),
    D.ul(db.items.map(item =>
      D.li({key: item.id}, item.text)
    )),
    D.button({gkey:'save'}, 'Save')
  ])
```

## 6. Mount
```js
app(body, db, orders).mount('#app')
```

## 7. Components — Reusable UI blocks
```js
// Register
component('user-card', (props, D) =>
  D.div({class:'card'}, [
    D.img({src: props.avatar}),
    D.h3(props.name)
  ])
)

// Use (camelCase or kebab-case both work)
D.userCard({ name: 'Ali', avatar: '/img/ali.jpg' })
```

## 8. Bridge — External libraries (Chart.js, Maps, Editors)
```js
// _bridge gives you the REAL DOM element.
// VDOM skips children of bridged elements.
// Return a cleanup function for destroy.
D.canvas({
  _bridge: (el) => {
    if (!el._chart) {
      el._chart = new Chart(el, config)  // first render: create
    } else {
      el._chart.data = newData           // updates: just refresh
      el._chart.update()
    }
    return () => el._chart.destroy()     // cleanup on unmount
  }
})
```

## 9. Raw HTML
```js
D.div({ _html: '<strong>Bold</strong> <em>italic</em>' })
D.div({ _html: marked.parse(db.markdown) })  // Markdown → HTML
```

## 10. Lazy Loading
```js
// Load external scripts on demand
MAS.load('https://cdn.jsdelivr.net/npm/chart.js').then(() => {
  myApp.set({ chartReady: true })
})

// Check if loaded
if (MAS.loaded('https://cdn.../chart.js')) { /* render chart */ }
```

## 11. ctx API
| Method | What |
|--------|------|
| `ctx.set({k:v})` | merge + re-render |
| `ctx.set(fn)` | functional update |
| `ctx.db` | current state |
| `ctx.batch(fn)` | group updates |
| `ctx.freeze()` | pause render |
| `ctx.unfreeze()` | resume render |

## 12. i18n (Optional)
Only needed if UI labels are client-side. With backend flatting, data arrives pre-translated.
```js
// If needed:
const db = {
  i18n: { dict: { save: { en:'Save', ar:'حفظ' } } }
}
// In body:
MAS.t(db, 'save') // → "حفظ"
```

## 13. Hooks (External observers)
```js
hook('onRender', ({db, root}) => console.log('rendered'))
hook('onState', ({prev, next}) => analytics.track(next))
hook('onError', ({error, gkey}) => sentry.capture(error))
```
