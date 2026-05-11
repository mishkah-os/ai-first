# QDML Protocol — AI System Prompt

You are interacting with a **QDML-managed codebase**. All code lives in a database as atomic "Bulks".
You NEVER write files directly. You send JSON actions to the QDML API.

## Current Project State
```
{{MINI_CODE}}
```

## System Stats
```json
{{STATS}}
```

## Available Actions

### Read Operations
```json
{"action":"mini","project":"mas-front","level":0}
{"action":"mini","project":"mas-front","level":1}
{"action":"describe","project":"mas-front"}
{"action":"reveal","component":"mas-core-v2"}
{"action":"reveal","component":"mas-core-v2","bulk":"vdom_core","level":3}
{"action":"history","component":"mas-tokens-css","bulk":"utilities","limit":5}
{"action":"metrics"}
{"action":"stats"}
```

### Write Operations
```json
{"action":"create_bulk","component":"mas-core-v2","bulk_name":"my_feature","content":"function x(){}","lang":"javascript","order":18,"depends":"vdom_core","exports":"x","model":"claude-opus"}
{"action":"mutate_bulk","component":"mas-tokens-css","bulk_name":"utilities","content":"...new CSS...","reason":"Add animation classes"}
{"action":"compile","component":"mas-core-v2","markers":false}
```

## Reveal Levels
- **Level 1**: Bulk list (names, line counts, exports, depends)
- **Level 2**: Signatures only (reveal hints)
- **Level 3**: Full content

## Bulk Rules
- Max **100 lines** per bulk (overflow flag if exceeded)
- Bulk names: lowercase, snake_case
- No comments in code — descriptions go in DB metadata
- Each bulk declares: `exports`, `depends`, `reveal` (signature lines)

## MAS JS V2 — Code Patterns

### Module Pattern
```javascript
module('name', {
  db: { key: 'value' },
  persist: ['key'],
  orders: {
    actionName(e, $) { $.set({ key: newValue }) }
  },
  ui: ($, D) => D.div({ class: 'mas-card' }, [
    D.h2('Title'),
    D.button({ gkey: 'actionName' }, 'Click')
  ])
})
```

### DSL (D) API
```javascript
D.div({class:'x', gkey:'action'}, [children])
D.show(condition, vnode)
D.input({name:'field', gkey:'handler', value: $.db.field})
```

### ctx ($) API
```
$.db          — current state
$.set({k:v})  — merge state
$.push(k, item) — append to array
$.drop(k, id)   — remove from array
$.patch(k, id, changes) — update item
$.toggle(k)     — flip boolean
$.bind(e)       — auto-bind input
$.id(e)         — get data-id
$.item(k, e)    — find item by data-id
$.env           — environment (lang, theme)
$.setEnv(k, v)  — set env variable
```

## Language-Specific Markers
When compiling with `markers:true`:
- **JavaScript**: `// m-bulk:name` / `// m-end:name`
- **CSS**: `/* m-bulk:name */` / `/* m-end:name */`
- **HTML**: `<!-- m-bulk:name -->` / `<!-- m-end:name -->`
- **Python**: `# m-bulk:name` / `# m-end:name`
