"""
Seed QDML Admin Dashboard into PostgreSQL.
A full MAS JS application built entirely via QDML protocol.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DATABASE_URL, QDML_SCHEMA
import asyncpg
from qdml_engine import QDMLEngine

# ════════════════════════════════════════════════════════════
# ADMIN DASHBOARD — 6 modules built with MAS JS V2
# ════════════════════════════════════════════════════════════

ADMIN_JS = {
"boot": {
    "order": 0,
    "exports": "API_URL,api,qdml",
    "depends": "",
    "reveal": "0:5",
    "content": r"""'use strict';
var API_URL = (location.origin.indexOf('localhost') > -1 || location.origin.indexOf('127.0.0.1') > -1)
  ? location.origin.replace(/:\d+/, ':8001')
  : location.origin + '/api';

function api(path, opts) {
  var token = localStorage.getItem('qdml_token');
  var headers = {'Content-Type': 'application/json'};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  return fetch(API_URL + path, Object.assign({headers: headers}, opts || {})).then(function(r) { return r.json(); });
}

function qdml(action) {
  return api('/api/qdml', {method: 'POST', body: JSON.stringify(action)});
}
"""
},

"auth_module": {
    "order": 1,
    "exports": "",
    "depends": "boot",
    "reveal": "0:3,10:12",
    "content": r"""MAS.module('auth', {
  db: {user: null, token: null, error: null, loading: false, form_user: '', form_pass: ''},
  persist: ['token', 'user'],

  orders: {
    'login': async function(e, $) {
      e.preventDefault();
      $.set({loading: true, error: null});
      var res = await api('/api/auth/login', {method: 'POST', body: JSON.stringify({username: $.db.form_user, password: $.db.form_pass})});
      if (res.ok) {
        localStorage.setItem('qdml_token', res.token);
        $.set({user: res.user, token: res.token, loading: false, error: null});
      } else {
        $.set({error: res.error || 'Login failed', loading: false});
      }
    },
    'logout': function(e, $) {
      localStorage.removeItem('qdml_token');
      $.set({user: null, token: null});
    },
    'input': function(e, $) { $.bind(e); }
  },

  ui: function($, D) {
    if ($.db.user) return null;
    return D.div({class: 'auth-overlay'}, [
      D.form({class: 'auth-card', gkey: 'auth.login', onsubmit: ''}, [
        D.h1({class: 'auth-title'}, 'QDML Platform'),
        D.p({class: 'auth-sub'}, 'Code lives in the database'),
        $.db.error ? D.div({class: 'auth-error'}, $.db.error) : null,
        D.input({type: 'text', name: 'form_user', placeholder: 'Username', value: $.db.form_user, gkey: 'auth.input', oninput: ''}),
        D.input({type: 'password', name: 'form_pass', placeholder: 'Password', value: $.db.form_pass, gkey: 'auth.input', oninput: ''}),
        D.button({type: 'submit', class: 'btn-primary', disabled: $.db.loading}, $.db.loading ? 'Connecting...' : 'Login')
      ])
    ]);
  },

  fetch: async function($) {
    var token = localStorage.getItem('qdml_token');
    if (token) {
      var res = await api('/api/auth/verify', {method: 'POST'});
      if (res.ok) $.set({user: res.user, token: token});
      else localStorage.removeItem('qdml_token');
    }
  }
});
"""
},

"nav_module": {
    "order": 2,
    "exports": "",
    "depends": "auth_module",
    "reveal": "0:3",
    "content": r"""MAS.module('nav', {
  db: {page: 'dashboard', collapsed: false},
  persist: ['page'],

  orders: {
    'go': function(e, $) { $.set({page: e.target.dataset.page || $.id(e)}); },
    'toggle': function(e, $) { $.toggle('collapsed'); }
  },

  ui: function($, D) {
    if (!$.root.auth || !$.root.auth.user) return null;
    var pages = [
      {id: 'dashboard', icon: '▣', label: 'Dashboard'},
      {id: 'projects', icon: '◆', label: 'Projects'},
      {id: 'bulks', icon: '■', label: 'Code'},
      {id: 'services', icon: '▲', label: 'Services'},
      {id: 'logs', icon: '○', label: 'Logs'}
    ];
    return D.aside({class: 'nav-sidebar' + ($.db.collapsed ? ' collapsed' : '')}, [
      D.div({class: 'nav-header'}, [
        D.span({class: 'nav-logo'}, 'Q'),
        $.db.collapsed ? null : D.span({class: 'nav-title'}, 'QDML')
      ]),
      D.nav({class: 'nav-list'},
        pages.map(function(p) {
          return D.a({class: 'nav-item' + ($.db.page === p.id ? ' active' : ''), 'data-id': p.id, gkey: 'nav.go'}, [
            D.span({class: 'nav-icon'}, p.icon),
            $.db.collapsed ? null : D.span(p.label)
          ]);
        })
      ),
      D.div({class: 'nav-footer'}, [
        D.a({gkey: 'nav.toggle', class: 'nav-item'}, $.db.collapsed ? '▶' : '◀'),
        D.a({gkey: 'auth.logout', class: 'nav-item nav-logout'}, [
          D.span({class: 'nav-icon'}, '✖'),
          $.db.collapsed ? null : D.span('Logout')
        ])
      ])
    ]);
  }
});
"""
},

"dashboard_module": {
    "order": 3,
    "exports": "",
    "depends": "boot,nav_module",
    "reveal": "0:3",
    "content": r"""MAS.module('dashboard', {
  db: {stats: null, mini: '', loading: false},

  orders: {
    'refresh': async function(e, $) {
      $.set({loading: true});
      var stats = await api('/api/qdml/stats').then(function(r) { return r.data; });
      var mini = await api('/api/qdml/mini/mas-front?level=1').then(function(r) { return r.data; });
      $.set({stats: stats, mini: mini, loading: false});
    }
  },

  ui: function($, D) {
    var s = $.db.stats;
    if (!s) return D.div({class: 'dashboard-empty'}, [
      D.h2('Dashboard'),
      D.button({gkey: 'dashboard.refresh', class: 'btn-primary'}, 'Load Data')
    ]);
    return D.div({class: 'dashboard'}, [
      D.h2('System Overview'),
      D.div({class: 'stats-grid'}, [
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, String(s.projects)), D.div({class: 'stat-label'}, 'Projects')]),
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, String(s.modules)), D.div({class: 'stat-label'}, 'Modules')]),
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, String(s.components)), D.div({class: 'stat-label'}, 'Components')]),
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, String(s.bulks)), D.div({class: 'stat-label'}, 'Bulks')]),
        D.div({class: 'stat-card highlight'}, [D.div({class: 'stat-value'}, String(s.total_lines)), D.div({class: 'stat-label'}, 'Total Lines')]),
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, String(s.operations)), D.div({class: 'stat-label'}, 'Operations')]),
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, String(s.history_snapshots)), D.div({class: 'stat-label'}, 'History')]),
        D.div({class: 'stat-card'}, [D.div({class: 'stat-value'}, s.db_size_mb + 'MB'), D.div({class: 'stat-label'}, 'DB Size')])
      ]),
      D.div({class: 'mini-code'}, [
        D.h3('Project Map'),
        D.pre({class: 'code-block'}, $.db.mini)
      ]),
      D.button({gkey: 'dashboard.refresh', class: 'btn-secondary'}, $.db.loading ? 'Loading...' : 'Refresh')
    ]);
  },

  fetch: async function($) {
    var stats = await api('/api/qdml/stats').then(function(r) { return r.data; });
    var mini = '';
    if (stats.projects > 0) mini = await api('/api/qdml/mini/mas-front?level=1').then(function(r) { return r.data; });
    $.set({stats: stats, mini: mini});
  }
});
"""
},

"bulks_module": {
    "order": 4,
    "exports": "",
    "depends": "boot,nav_module",
    "reveal": "0:5",
    "content": r"""MAS.module('bulks', {
  db: {projects: [], modules: [], components: [], bulkList: [], selected_project: null, selected_comp: null, selected_bulk: null, content: '', loading: false},

  orders: {
    'load': async function(e, $) {
      $.set({loading: true});
      var res = await qdml({action: 'describe'});
      if (res.ok && res.data.length) {
        var proj = res.data;
        $.set({projects: proj, loading: false});
      } else {
        $.set({loading: false});
      }
    },
    'select-project': async function(e, $) {
      var slug = $.id(e);
      var proj = $.db.projects.find(function(p) { return p.slug === slug; });
      if (!proj) return;
      var comps = [];
      proj.modules.forEach(function(m) { m.components.forEach(function(c) { comps.push({slug: c.slug, name: c.name, module: m.slug, bulks: c.bulks}); }); });
      $.set({selected_project: slug, components: comps, selected_comp: null, bulkList: [], content: ''});
    },
    'select-comp': async function(e, $) {
      var slug = $.id(e);
      var comp = $.db.components.find(function(c) { return c.slug === slug; });
      if (!comp) return;
      $.set({selected_comp: slug, bulkList: comp.bulks, selected_bulk: null, content: ''});
    },
    'select-bulk': async function(e, $) {
      var name = $.id(e);
      $.set({loading: true, selected_bulk: name});
      var res = await qdml({action: 'reveal', component: $.db.selected_comp, bulk: name, level: 3, project: $.db.selected_project});
      $.set({content: res.ok ? res.data.content : 'Error: ' + res.error, loading: false});
    },
    'compile': async function(e, $) {
      if (!$.db.selected_comp) return;
      $.set({loading: true});
      var res = await qdml({action: 'compile', component: $.db.selected_comp, project: $.db.selected_project});
      $.set({content: res.ok ? res.data : 'Error: ' + res.error, selected_bulk: '[compiled]', loading: false});
    }
  },

  ui: function($, D) {
    return D.div({class: 'bulks-panel'}, [
      D.h2('Code Explorer'),
      D.div({class: 'bulks-toolbar'}, [
        D.button({gkey: 'bulks.load', class: 'btn-primary'}, $.db.loading ? 'Loading...' : 'Load Projects'),
        $.db.selected_comp ? D.button({gkey: 'bulks.compile', class: 'btn-secondary'}, 'Compile') : null
      ]),
      D.div({class: 'bulks-layout'}, [
        D.div({class: 'bulks-sidebar'}, [
          $.db.projects.length ? D.div({class: 'panel-section'}, [
            D.h4('Projects'),
            D.div({class: 'item-list'}, $.db.projects.map(function(p) {
              return D.a({class: 'list-item' + ($.db.selected_project === p.slug ? ' active' : ''), 'data-id': p.slug, gkey: 'bulks.select-project'}, p.name);
            }))
          ]) : null,
          $.db.components.length ? D.div({class: 'panel-section'}, [
            D.h4('Components'),
            D.div({class: 'item-list'}, $.db.components.map(function(c) {
              return D.a({class: 'list-item' + ($.db.selected_comp === c.slug ? ' active' : ''), 'data-id': c.slug, gkey: 'bulks.select-comp'}, [
                D.span(c.name),
                D.small(' (' + c.bulks.length + ' bulks)')
              ]);
            }))
          ]) : null,
          $.db.bulkList.length ? D.div({class: 'panel-section'}, [
            D.h4('Bulks'),
            D.div({class: 'item-list'}, $.db.bulkList.map(function(b) {
              return D.a({class: 'list-item' + ($.db.selected_bulk === b.name ? ' active' : ''), 'data-id': b.name, gkey: 'bulks.select-bulk'}, [
                D.span(b.name),
                D.small(' ' + b.lines + 'L')
              ]);
            }))
          ]) : null
        ]),
        D.div({class: 'bulks-content'}, [
          $.db.selected_bulk ? D.div({class: 'content-header'}, [
            D.span({class: 'content-title'}, $.db.selected_comp + ' / ' + $.db.selected_bulk)
          ]) : null,
          D.pre({class: 'code-viewer'}, $.db.content || '// Select a bulk to view code')
        ])
      ])
    ]);
  },

  fetch: async function($) {
    var res = await qdml({action: 'describe'});
    if (res.ok && res.data.length) $.set({projects: res.data});
  }
});
"""
},

"services_module": {
    "order": 5,
    "exports": "",
    "depends": "boot,nav_module",
    "reveal": "0:3",
    "content": r"""MAS.module('services', {
  db: {list: [], loading: false},

  orders: {
    'refresh': async function(e, $) {
      $.set({loading: true});
      var res = await api('/api/qdml/stats');
      $.set({list: [
        {name: 'QDML Core', port: 8001, protocol: 'http', status: res.ok ? 'active' : 'error'},
        {name: 'WS Relay', port: 8003, protocol: 'ws', status: 'planned'},
        {name: 'Quantum Core', port: 0, protocol: 'stdio', status: 'planned'},
        {name: 'Bun SSR', port: 8004, protocol: 'http', status: 'planned'}
      ], loading: false});
    }
  },

  ui: function($, D) {
    return D.div({class: 'services-panel'}, [
      D.h2('Microservices'),
      D.button({gkey: 'services.refresh', class: 'btn-primary'}, 'Check Status'),
      $.db.list.length ? D.table({class: 'data-table'}, [
        D.thead([D.tr([D.th('Service'), D.th('Port'), D.th('Protocol'), D.th('Status')])]),
        D.tbody($.db.list.map(function(s) {
          return D.tr([
            D.td(D.strong(s.name)),
            D.td(String(s.port || '—')),
            D.td(s.protocol),
            D.td(D.span({class: 'status-badge status-' + s.status}, s.status))
          ]);
        }))
      ]) : null
    ]);
  },

  fetch: async function($) {
    var res = await api('/api/qdml/stats');
    $.set({list: [
      {name: 'QDML Core', port: 8001, protocol: 'http', status: res.ok ? 'active' : 'error'},
      {name: 'WS Relay', port: 8003, protocol: 'ws', status: 'planned'},
      {name: 'Quantum Core', port: 0, protocol: 'stdio', status: 'planned'},
      {name: 'Bun SSR', port: 8004, protocol: 'http', status: 'planned'}
    ]});
  }
});
"""
},

"logs_module": {
    "order": 6,
    "exports": "",
    "depends": "boot,nav_module",
    "reveal": "0:3",
    "content": r"""MAS.module('logs', {
  db: {metrics: [], recent: [], loading: false},

  orders: {
    'refresh': async function(e, $) {
      $.set({loading: true});
      var m = await qdml({action: 'metrics'});
      var r = await qdml({action: 'recent_ops', limit: 30});
      $.set({metrics: m.ok ? m.data : [], recent: r.ok ? r.data : [], loading: false});
    }
  },

  ui: function($, D) {
    return D.div({class: 'logs-panel'}, [
      D.h2('Operations Log'),
      D.button({gkey: 'logs.refresh', class: 'btn-primary'}, $.db.loading ? 'Loading...' : 'Refresh'),
      $.db.metrics.length ? D.div([
        D.h3('Metrics'),
        D.table({class: 'data-table'}, [
          D.thead([D.tr([D.th('Operation'), D.th('Count'), D.th('OK'), D.th('Fail'), D.th('Avg ms'), D.th('Total ms')])]),
          D.tbody($.db.metrics.map(function(m) {
            return D.tr([D.td(m.operation), D.td(String(m.count)), D.td(String(m.ok)), D.td(String(m.fail)), D.td(String(m.avg_ms)), D.td(String(m.total_ms))]);
          }))
        ])
      ]) : null,
      $.db.recent.length ? D.div([
        D.h3('Recent (' + $.db.recent.length + ')'),
        D.table({class: 'data-table compact'}, [
          D.thead([D.tr([D.th('Op'), D.th('Service'), D.th('Actor'), D.th('ms'), D.th('Time')])]),
          D.tbody($.db.recent.slice(0, 20).map(function(r) {
            var t = r.ts ? new Date(r.ts).toLocaleTimeString() : '';
            return D.tr({class: r.success ? '' : 'row-error'}, [
              D.td(r.operation), D.td(r.service), D.td(r.actor),
              D.td(String(r.duration_ms ? r.duration_ms.toFixed(1) : '—')), D.td(t)
            ]);
          }))
        ])
      ]) : null
    ]);
  },

  fetch: async function($) {
    var m = await qdml({action: 'metrics'});
    var r = await qdml({action: 'recent_ops', limit: 30});
    $.set({metrics: m.ok ? m.data : [], recent: r.ok ? r.data : []});
  }
});
"""
},

"app_mount": {
    "order": 7,
    "exports": "app",
    "depends": "auth_module,nav_module,dashboard_module,bulks_module,services_module,logs_module",
    "reveal": "0:10",
    "content": r"""var body = function(db, D) {
  if (!db.auth || !db.auth.user) return D.auth();
  var page = (db.nav && db.nav.page) || 'dashboard';
  return D.div({class: 'app-shell'}, [
    D.nav(),
    D.main({class: 'app-main'}, [
      page === 'dashboard' ? D.dashboard() : null,
      page === 'projects' ? D.dashboard() : null,
      page === 'bulks' ? D.bulks() : null,
      page === 'services' ? D.services() : null,
      page === 'logs' ? D.logs() : null
    ])
  ]);
};

var app = MAS.app(body, {}).mount('#app');
"""
}
}

ADMIN_CSS = {
"variables": {
    "order": 0,
    "content": r""":root {
  --bg-primary: #0f0f14;
  --bg-secondary: #1a1a24;
  --bg-card: #22222e;
  --bg-hover: #2a2a3a;
  --text-primary: #e8e8f0;
  --text-secondary: #8888a0;
  --text-muted: #555570;
  --accent: #6366f1;
  --accent-hover: #818cf8;
  --accent-glow: rgba(99, 102, 241, 0.15);
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;
  --border: #2a2a3a;
  --radius: 8px;
  --radius-lg: 12px;
  --font: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --shadow: 0 4px 20px rgba(0,0,0,0.3);
}
"""
},
"reset_base": {
    "order": 1,
    "content": r"""*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: var(--font); background: var(--bg-primary); color: var(--text-primary); font-size: 14px; }
a { color: inherit; text-decoration: none; cursor: pointer; }
button { cursor: pointer; border: none; font: inherit; }
input, textarea { font: inherit; border: none; outline: none; }
pre { font-family: var(--font-mono); white-space: pre-wrap; word-break: break-all; }
table { width: 100%; border-collapse: collapse; }
"""
},
"layout": {
    "order": 2,
    "content": r""".app-shell { display: flex; height: 100vh; overflow: hidden; }
.app-main { flex: 1; padding: 24px 32px; overflow-y: auto; }
.nav-sidebar { width: 220px; background: var(--bg-secondary); border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 16px 0; }
.nav-sidebar.collapsed { width: 60px; }
.nav-header { display: flex; align-items: center; gap: 10px; padding: 8px 16px; margin-bottom: 24px; }
.nav-logo { font-size: 24px; font-weight: 800; color: var(--accent); }
.nav-title { font-size: 18px; font-weight: 700; }
.nav-list { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-radius: var(--radius); margin: 0 8px; transition: background 0.15s; }
.nav-item:hover { background: var(--bg-hover); }
.nav-item.active { background: var(--accent-glow); color: var(--accent); }
.nav-icon { font-size: 16px; width: 20px; text-align: center; }
.nav-footer { margin-top: auto; padding-top: 16px; border-top: 1px solid var(--border); }
.nav-logout:hover { color: var(--error); }
"""
},
"auth_styles": {
    "order": 3,
    "content": r""".auth-overlay { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: var(--bg-primary); }
.auth-card { background: var(--bg-card); padding: 40px; border-radius: var(--radius-lg); box-shadow: var(--shadow); width: 360px; display: flex; flex-direction: column; gap: 16px; border: 1px solid var(--border); }
.auth-title { font-size: 24px; font-weight: 700; text-align: center; background: linear-gradient(135deg, var(--accent), #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.auth-sub { text-align: center; color: var(--text-secondary); font-size: 13px; }
.auth-error { background: rgba(239,68,68,0.1); border: 1px solid var(--error); color: var(--error); padding: 8px 12px; border-radius: var(--radius); font-size: 13px; }
.auth-card input { background: var(--bg-primary); border: 1px solid var(--border); padding: 12px 14px; border-radius: var(--radius); color: var(--text-primary); width: 100%; }
.auth-card input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }
"""
},
"components_styles": {
    "order": 4,
    "content": r""".btn-primary { background: var(--accent); color: white; padding: 10px 20px; border-radius: var(--radius); font-weight: 500; transition: background 0.15s; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--bg-hover); color: var(--text-primary); padding: 10px 20px; border-radius: var(--radius); font-weight: 500; }
.btn-secondary:hover { background: var(--border); }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin: 20px 0; }
.stat-card { background: var(--bg-card); padding: 16px; border-radius: var(--radius); border: 1px solid var(--border); text-align: center; }
.stat-card.highlight { border-color: var(--accent); background: var(--accent-glow); }
.stat-value { font-size: 24px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 11px; color: var(--text-secondary); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }

.data-table { margin: 16px 0; }
.data-table th { text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase; color: var(--text-muted); border-bottom: 1px solid var(--border); }
.data-table td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
.data-table tr:hover td { background: var(--bg-hover); }
.data-table.compact td, .data-table.compact th { padding: 5px 8px; font-size: 12px; }
.row-error td { color: var(--error); }

.status-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.status-active { background: rgba(34,197,94,0.15); color: var(--success); }
.status-planned { background: rgba(245,158,11,0.15); color: var(--warning); }
.status-error { background: rgba(239,68,68,0.15); color: var(--error); }
"""
},
"bulks_styles": {
    "order": 5,
    "content": r""".bulks-panel { display: flex; flex-direction: column; height: calc(100vh - 80px); }
.bulks-toolbar { display: flex; gap: 8px; margin-bottom: 16px; }
.bulks-layout { display: flex; gap: 16px; flex: 1; overflow: hidden; }
.bulks-sidebar { width: 260px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
.bulks-content { flex: 1; display: flex; flex-direction: column; }
.panel-section h4 { font-size: 11px; text-transform: uppercase; color: var(--text-muted); padding: 0 4px; margin-bottom: 6px; }
.item-list { display: flex; flex-direction: column; gap: 2px; }
.list-item { display: flex; align-items: center; justify-content: space-between; padding: 7px 10px; border-radius: var(--radius); font-size: 13px; }
.list-item:hover { background: var(--bg-hover); }
.list-item.active { background: var(--accent-glow); color: var(--accent); }
.list-item small { color: var(--text-muted); font-size: 11px; }
.content-header { padding: 8px 12px; background: var(--bg-secondary); border-radius: var(--radius) var(--radius) 0 0; border: 1px solid var(--border); border-bottom: none; }
.content-title { font-size: 12px; font-weight: 600; color: var(--accent); font-family: var(--font-mono); }
.code-viewer { flex: 1; background: var(--bg-card); border: 1px solid var(--border); border-radius: 0 0 var(--radius) var(--radius); padding: 16px; overflow: auto; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; color: var(--text-secondary); }
.code-block { background: var(--bg-card); border: 1px solid var(--border); padding: 16px; border-radius: var(--radius); font-size: 12px; line-height: 1.5; overflow-x: auto; }
.mini-code { margin: 20px 0; }
.dashboard-empty { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 60px; }
.services-panel, .logs-panel { padding-bottom: 40px; }
.services-panel h2, .logs-panel h2, .bulks-panel h2, .dashboard h2 { margin-bottom: 16px; }
"""
}
}

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QDML Platform</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/lib/admin.css">
</head>
<body>
<div id="app"></div>
<script src="/lib/mas.core.js"></script>
<script src="/lib/admin.js"></script>
</body>
</html>"""


async def main():
    print("=" * 60)
    print("QDML SEED — Admin Dashboard (MAS JS Native)")
    print("=" * 60)

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"}
    )
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ MODULE: Admin App ═══
    print("\n[1/5] Creating admin module...")
    await engine.create_module("mas-front", "Admin Dashboard", "admin-app", tier="frontend", app="admin")

    # ═══ COMPONENTS ═══
    print("[2/5] Creating components...")
    await engine.create_component("admin-app", "Admin JS", "admin-js", kind="library", target="mas-js", project_slug="mas-front")
    await engine.create_component("admin-app", "Admin CSS", "admin-css", kind="library", target="mas-js", project_slug="mas-front")
    await engine.create_component("admin-app", "Admin HTML", "admin-html", kind="screen", target="mas-js", project_slug="mas-front")

    # ═══ JS BULKS ═══
    print("[3/5] Registering JS bulks (8 modules)...")
    for name, data in ADMIN_JS.items():
        await engine.create_bulk(
            "admin-js", name, data["content"], lang="javascript",
            bulk_order=data["order"], reveal=data.get("reveal", ""),
            depends=data.get("depends", ""), exports=data.get("exports", ""),
            project_slug="mas-front"
        )
    print(f"       {len(ADMIN_JS)} JS bulks")

    # ═══ CSS BULKS ═══
    print("[4/5] Registering CSS bulks...")
    for name, data in ADMIN_CSS.items():
        await engine.create_bulk(
            "admin-css", name, data["content"], lang="css",
            bulk_order=data["order"],
            project_slug="mas-front"
        )
    print(f"       {len(ADMIN_CSS)} CSS bulks")

    # ═══ HTML ARTIFACT ═══
    print("[5/5] Registering HTML shell...")
    await engine.create_bulk("admin-html", "shell", ADMIN_HTML, lang="html", project_slug="mas-front")

    # ═══ COMPILE & WRITE ═══
    print("\n--- Compiling to _generated/ ---")
    import pathlib
    gen_dir = pathlib.Path(__file__).parent.parent / "mas-front" / "_generated"
    gen_dir.mkdir(parents=True, exist_ok=True)

    js_code = await engine.compile_component("admin-js", project_slug="mas-front")
    css_code = await engine.compile_component("admin-css", project_slug="mas-front")
    html_code = await engine.compile_component("admin-html", project_slug="mas-front")
    mas_core = await engine.compile_component("mas-core-v2", project_slug="mas-front")

    (gen_dir / "admin.js").write_text(js_code, encoding="utf-8")
    (gen_dir / "admin.css").write_text(css_code, encoding="utf-8")
    (gen_dir / "index.html").write_text(html_code, encoding="utf-8")
    (gen_dir / "mas.core.js").write_text(mas_core, encoding="utf-8")

    print(f"  admin.js:   {js_code.count(chr(10))+1} lines")
    print(f"  admin.css:  {css_code.count(chr(10))+1} lines")
    print(f"  index.html: {html_code.count(chr(10))+1} lines")
    print(f"  mas.core.js: {mas_core.count(chr(10))+1} lines")

    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {stats['projects']} projects | {stats['modules']} modules | {stats['components']} components | {stats['bulks']} bulks | {stats['total_lines']} lines")
    print(f"{'=' * 60}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
