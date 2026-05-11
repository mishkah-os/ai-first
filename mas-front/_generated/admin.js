'use strict';
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

MAS.module('auth', {
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

MAS.module('nav', {
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

MAS.module('dashboard', {
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

MAS.module('bulks', {
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

MAS.module('services', {
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

MAS.module('logs', {
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

var body = function(db, D) {
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
