const { D, app, module } = MAS

const API = '/api'

async function api(path, opts = {}) {
  const token = localStorage.getItem('qdml_token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = 'Bearer ' + token
  const res = await fetch(API + path, {
    method: opts.method || 'POST',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined
  })
  return res.json()
}

async function qdml(action) {
  return api('/qdml', { body: action })
}

module('auth', {
  db: { user: null, token: '', error: '', loading: false, form_user: '', form_pass: '' },
  persist: ['token', 'user'],
  orders: {
    input: { on: ['input'], do(e, $) { $.bind(e) } },
    login: { on: ['click', 'keydown'], do: async function(e, $) {
      if (e.type === 'keydown' && e.key !== 'Enter') return
      $.set({ loading: true, error: '' })
      const res = await api('/auth/login', { body: { username: $.db.form_user, password: $.db.form_pass } })
      if (res.ok) {
        localStorage.setItem('qdml_token', res.token)
        $.set({ user: res.user, token: res.token, loading: false, form_user: '', form_pass: '' })
      } else {
        $.set({ error: res.error || 'Login failed', loading: false })
      }
    }},
    logout(e, $) {
      api('/auth/logout')
      localStorage.removeItem('qdml_token')
      $.set({ user: null, token: '', form_user: '', form_pass: '' })
    }
  },
  ui: ($, D) => {
    return D.div({ class: 'admin-login' }, [
      D.div({ class: 'admin-login-box' }, [
        D.div({ class: 'admin-login-logo' }, 'QDML'),
        D.div({ class: 'admin-login-sub' }, 'AI-First Code Kernel'),
        $.db.error ? D.div({ class: 'admin-login-error' }, $.db.error) : null,
        D.input({ name: 'form_user', gkey: 'auth.input', class: 'admin-login-field', placeholder: 'Username', value: $.db.form_user, autocomplete: 'username' }),
        D.input({ name: 'form_pass', gkey: 'auth.login', type: 'password', class: 'admin-login-field', placeholder: 'Password', value: $.db.form_pass, autocomplete: 'current-password' }),
        D.button({ gkey: 'auth.login', class: 'admin-login-btn', disabled: $.db.loading }, $.db.loading ? 'Connecting...' : 'Login')
      ])
    ])
  }
})

module('nav', {
  db: { page: 'dashboard' },
  orders: {
    go(e, $) {
      const page = $.id(e) || 'dashboard'
      $.set({ page })
    }
  }
})

module('dashboard', {
  db: { stats: null, mini: '', loading: false },
  orders: {
    async refresh(e, $) {
      $.set({ loading: true })
      const [statsRes, miniRes] = await Promise.all([
        qdml({ action: 'stats' }),
        qdml({ action: 'mini', project: 'mas-front', level: 1 })
      ])
      $.set({
        stats: statsRes.ok ? statsRes.data : null,
        mini: miniRes.ok ? miniRes.data : 'No data',
        loading: false
      })
    }
  },
  ui: ($, D) => {
    const s = $.db.stats
    if (!s) return D.div({ class: 'admin-empty' }, [
      D.div('Loading...'),
      D.button({ gkey: 'dashboard.refresh', class: 'admin-btn admin-btn-primary', style: 'margin-top:16px' }, 'Load Dashboard')
    ])
    return D.div([
      D.div({ class: 'admin-stats' }, [
        statCard('Modules', s.modules, '📦'),
        statCard('Components', s.components, '🧩'),
        statCard('Bulks', s.bulks, '📄'),
        statCard('Lines', s.total_lines.toLocaleString(), '📏'),
        statCard('Operations', s.operations, '⚡'),
        statCard('History', s.history_snapshots, '📸'),
        statCard('DB Size', s.db_size_kb + ' KB', '💾'),
        statCard('Projects', s.projects, '🏗️')
      ]),
      D.div({ class: 'admin-section-title' }, ['📋 Mini-Code (Level 1)', D.button({ gkey: 'dashboard.refresh', class: 'admin-btn admin-btn-ghost', style: 'margin-left:auto;font-size:12px' }, '↻ Refresh')]),
      D.div({ class: 'admin-minicode' }, $.db.mini)
    ])
  }
})

module('bulks', {
  db: { components: [], bulkList: [], selected: null, content: '', compSlug: '', loading: false },
  orders: {
    async loadComps(e, $) {
      $.set({ loading: true })
      const res = await qdml({ action: 'describe', project: 'mas-front' })
      if (res.ok && res.data && res.data[0]) {
        const comps = []
        res.data[0].modules.forEach(m => {
          m.components.forEach(c => comps.push({ slug: c.slug, name: c.name, kind: c.kind, bulks: c.bulks }))
        })
        $.set({ components: comps, loading: false })
        if (comps.length && !$.db.compSlug) {
          $.set({ compSlug: comps[0].slug, bulkList: comps[0].bulks })
        }
      }
    },
    selectComp(e, $) {
      const slug = $.id(e)
      const comp = $.db.components.find(c => c.slug === slug)
      if (comp) $.set({ compSlug: slug, bulkList: comp.bulks, selected: null, content: '' })
    },
    async selectBulk(e, $) {
      const name = $.id(e)
      $.set({ loading: true })
      const res = await qdml({ action: 'reveal', component: $.db.compSlug, bulk: name, level: 3 })
      if (res.ok) $.set({ selected: name, content: res.data.content || '', loading: false })
      else $.set({ loading: false })
    },
    async compile(e, $) {
      $.set({ loading: true })
      const res = await qdml({ action: 'compile', component: $.db.compSlug, markers: false })
      if (res.ok) $.set({ selected: '_compiled', content: res.data, loading: false })
      else $.set({ loading: false })
    }
  },
  ui: ($, D) => {
    const comps = $.db.components
    if (!comps.length) return D.div({ class: 'admin-empty' }, [
      D.button({ gkey: 'bulks.loadComps', class: 'admin-btn admin-btn-primary' }, 'Load Components')
    ])
    return D.div([
      D.div({ class: 'admin-comp-selector' },
        comps.map(c => D.button({
          'data-id': c.slug, gkey: 'bulks.selectComp',
          class: 'admin-comp-btn' + ($.db.compSlug === c.slug ? ' active' : '')
        }, c.slug + ' (' + c.bulks.length + ')'))
      ),
      D.div({ style: 'display:flex;gap:16px' }, [
        D.div({ style: 'width:280px;flex-shrink:0' }, [
          D.div({ class: 'admin-section-title' }, ['Bulks', D.button({ gkey: 'bulks.compile', class: 'admin-btn admin-btn-ghost', style: 'margin-left:auto;font-size:11px;padding:4px 10px' }, 'Compile')]),
          D.div({ class: 'admin-bulk-list' },
            $.db.bulkList.map(b => D.div({
              'data-id': b.name, gkey: 'bulks.selectBulk',
              class: 'admin-bulk-item' + ($.db.selected === b.name ? ' selected' : '')
            }, [
              D.span({ class: 'admin-bulk-name' }, b.name),
              D.span({ class: 'admin-bulk-meta' }, [
                D.span(b.lines + 'L'),
                D.span(b.chars + 'c')
              ])
            ]))
          )
        ]),
        D.div({ style: 'flex:1;min-width:0' }, [
          $.db.selected
            ? D.div([
                D.div({ class: 'admin-section-title' }, [
                  $.db.selected === '_compiled' ? 'Compiled Output' : $.db.selected,
                  $.db.selected !== '_compiled' ? D.span({ class: 'admin-badge admin-badge-info', style: 'margin-left:8px' }, $.db.content.split('\n').length + ' lines') : null
                ]),
                D.div({ class: 'admin-code-viewer' }, $.db.content)
              ])
            : D.div({ class: 'admin-empty' }, 'Select a bulk to view')
        ])
      ])
    ])
  }
})

module('logs', {
  db: { metrics: [], recent: [], loading: false },
  orders: {
    async refresh(e, $) {
      $.set({ loading: true })
      const [mRes, rRes] = await Promise.all([
        qdml({ action: 'metrics' }),
        qdml({ action: 'recent_ops', limit: 30 })
      ])
      $.set({
        metrics: mRes.ok ? mRes.data : [],
        recent: rRes.ok ? rRes.data : [],
        loading: false
      })
    }
  },
  ui: ($, D) => {
    if (!$.db.metrics.length) return D.div({ class: 'admin-empty' }, [
      D.button({ gkey: 'logs.refresh', class: 'admin-btn admin-btn-primary' }, 'Load Logs')
    ])
    return D.div([
      D.div({ class: 'admin-section-title' }, ['📊 Operation Metrics', D.button({ gkey: 'logs.refresh', class: 'admin-btn admin-btn-ghost', style: 'margin-left:auto;font-size:12px' }, '↻')]),
      D.div({ class: 'admin-table-wrap', style: 'margin-bottom:24px' }, [
        D.table({ class: 'admin-table' }, [
          D.thead(D.tr([
            D.th('Operation'), D.th('Count'), D.th('OK'), D.th('Fail'), D.th('Avg (ms)'), D.th('Total (ms)')
          ])),
          D.tbody($.db.metrics.map(m =>
            D.tr([
              D.td(D.span({ class: 'admin-bulk-name' }, m.operation)),
              D.td(String(m.count)),
              D.td(D.span({ class: 'admin-badge admin-badge-ok' }, String(m.ok))),
              D.td(m.fail > 0 ? D.span({ class: 'admin-badge admin-badge-fail' }, String(m.fail)) : '-'),
              D.td(String(m.avg_ms)),
              D.td(String(m.total_ms))
            ])
          ))
        ])
      ]),
      D.div({ class: 'admin-section-title' }, '📜 Recent Operations (last 30)'),
      D.div({ class: 'admin-table-wrap' }, [
        D.table({ class: 'admin-table' }, [
          D.thead(D.tr([
            D.th('Operation'), D.th('Module'), D.th('Status'), D.th('Duration'), D.th('Time')
          ])),
          D.tbody($.db.recent.map(r =>
            D.tr([
              D.td(r.operation),
              D.td(r.module || '-'),
              D.td(r.success ? D.span({ class: 'admin-badge admin-badge-ok' }, 'OK') : D.span({ class: 'admin-badge admin-badge-fail' }, r.error_msg || 'FAIL')),
              D.td(r.duration_ms ? (r.duration_ms.toFixed(2) + 'ms') : '-'),
              D.td(D.span({ style: 'font-size:11px;color:var(--mas-text-muted)' }, r.started_at ? r.started_at.slice(11, 19) : ''))
            ])
          ))
        ])
      ])
    ])
  }
})

function statCard(label, value, icon) {
  return D.div({ class: 'admin-stat-card' }, [
    D.span({ class: 'admin-stat-icon' }, icon),
    D.div({ class: 'admin-stat-label' }, label),
    D.div({ class: 'admin-stat-value' }, String(value))
  ])
}

const NAV_ITEMS = [
  { id: 'dashboard', icon: '📊', label: 'Dashboard' },
  { id: 'bulks',     icon: '📦', label: 'Bulks' },
  { id: 'logs',      icon: '📜', label: 'Operation Logs' }
]

const body = (db) => {
  if (!db.auth || !db.auth.user) return D.auth()
  const page = (db.nav && db.nav.page) || 'dashboard'
  const user = db.auth.user
  return D.div({ class: 'admin-shell' }, [
    D.aside({ class: 'admin-sidebar' }, [
      D.div({ class: 'admin-sidebar-brand' }, [
        D.span({ class: 'admin-sidebar-brand-text' }, 'QDML'),
        D.span({ class: 'admin-sidebar-brand-ver' }, 'v2')
      ]),
      D.nav({ class: 'admin-sidebar-nav' },
        NAV_ITEMS.map(n => D.div({
          'data-id': n.id, gkey: 'nav.go',
          class: 'admin-nav-item' + (page === n.id ? ' active' : '')
        }, [
          D.span({ class: 'admin-nav-icon' }, n.icon),
          D.span(n.label)
        ]))
      ),
      D.div({ class: 'admin-sidebar-user' }, [
        D.div({ class: 'admin-user-avatar' }, (user.display_name || user.username || 'A')[0].toUpperCase()),
        D.div([
          D.div({ class: 'admin-user-name' }, user.display_name || user.username),
          D.div({ class: 'admin-user-role' }, user.role || 'admin')
        ]),
        D.button({ gkey: 'auth.logout', class: 'admin-btn admin-btn-ghost', style: 'margin-left:auto;padding:4px 8px;font-size:11px' }, '↪')
      ])
    ]),
    D.div({ class: 'admin-main' }, [
      D.header({ class: 'admin-header' }, [
        D.h1({ class: 'admin-header-title' }, NAV_ITEMS.find(n => n.id === page)?.label || 'QDML'),
        D.div({ class: 'admin-header-actions' }, [
          D.span({ style: 'font-size:12px;color:var(--mas-text-muted)' }, 'AI-First Kernel')
        ])
      ]),
      D.main({ class: 'admin-content' }, [
        page === 'dashboard' ? D.dashboard() : null,
        page === 'bulks' ? D.bulks() : null,
        page === 'logs' ? D.logs() : null
      ])
    ])
  ])
}

const myApp = app(body, {
  env: { lang: 'en', theme: 'dark' },
  persistEnv: ['lang', 'theme']
}).mount('#app')
