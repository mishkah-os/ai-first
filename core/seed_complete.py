#!/usr/bin/env python3
"""
Complete seeding: mas-store, kits, pipeline, ERP, mostamal-hawaa
"""
import asyncio
import asyncpg
import json
from pathlib import Path
from qdml_engine import QDMLEngine
from config import DATABASE_URL, QDML_SCHEMA


# ═══════════════════════════════════════════════════════
# mas-store UNIFIED LIBRARY
# ═══════════════════════════════════════════════════════

MAS_STORE_BULKS = {
"core": {
    "order": 0, "lang": "javascript",
    "exports": "MasStore,masStore",
    "depends": "",
    "content": r"""// mas-store v3 Unified — Core + IndexedDB + WS + Outbox
const DB_NAME = 'mas-store';
const DB_VERSION = 3;
const STORES = { entities: 'id', outbox: '++id', cursors: 'table', cache: 'key' };

let db = null;
let ws = null;
let config = {
    wsUrl: window.MAS_WS_URL || 'ws://localhost:8003',
    apiUrl: window.MAS_API_URL || '/api',
    syncInterval: 5000,
    outboxRetry: 3000
};

// ─── IndexedDB ───
async function openDB() {
    if (db) return db;
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = (e) => {
            const d = e.target.result;
            for (const [name, key] of Object.entries(STORES)) {
                if (!d.objectStoreNames.contains(name)) {
                    d.createObjectStore(name, { keyPath: key.startsWith('++') ? undefined : key, autoIncrement: key.startsWith('++') });
                }
            }
        };
        req.onsuccess = (e) => { db = e.target.result; resolve(db); };
        req.onerror = reject;
    });
}

async function idbGet(store, key) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readonly');
        const req = tx.objectStore(store).get(key);
        req.onsuccess = () => res(req.result);
        req.onerror = rej;
    });
}

async function idbPut(store, value) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readwrite');
        const req = tx.objectStore(store).put(value);
        req.onsuccess = () => res(req.result);
        req.onerror = rej;
    });
}

async function idbDelete(store, key) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readwrite');
        const req = tx.objectStore(store).delete(key);
        req.onsuccess = () => res();
        req.onerror = rej;
    });
}

async function idbGetAll(store) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readonly');
        const req = tx.objectStore(store).getAll();
        req.onsuccess = () => res(req.result);
        req.onerror = rej;
    });
}
"""
},

"websocket": {
    "order": 1, "lang": "javascript",
    "exports": "connectWS,disconnectWS,requestSync",
    "depends": "core",
    "content": r"""// ─── WebSocket Delta Sync ───
let reconnectAttempts = 0;

async function connectWS(projectId) {
    if (ws && ws.readyState === WebSocket.OPEN) return ws;

    return new Promise((resolve, reject) => {
        ws = new WebSocket(config.wsUrl);

        ws.onopen = () => {
            reconnectAttempts = 0;
            ws.send(JSON.stringify({ type: 'subscribe', project_id: projectId }));
            resolve(ws);
        };

        ws.onmessage = async (event) => {
            const msg = JSON.parse(event.data);
            await handleWSMessage(msg);
        };

        ws.onclose = () => {
            ws = null;
            if (reconnectAttempts < 5) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts++), 30000);
                setTimeout(() => connectWS(projectId), delay);
            }
        };

        ws.onerror = reject;
    });
}

function disconnectWS() {
    if (ws) { ws.close(); ws = null; }
}

async function handleWSMessage(msg) {
    switch (msg.type) {
        case 'change':
            await applyRemoteChange(msg);
            break;
        case 'sync_response':
            for (const [table, data] of Object.entries(msg.data || {})) {
                for (const change of data.changes || []) {
                    await applyRemoteChange({ table, ...change });
                }
                if (data.latest_cursor) {
                    await idbPut('cursors', { table, cursor: data.latest_cursor });
                }
            }
            break;
    }
}

async function applyRemoteChange(change) {
    const { table, record_id, action, delta, tombstone } = change;
    const key = `${table}:${record_id}`;

    if (action === 'delete' || tombstone) {
        await idbDelete('entities', key);
    } else {
        const existing = await idbGet('entities', key);
        const entity = existing ? { ...existing, ...delta } : { id: key, ...delta };
        entity._table = table;
        entity._record_id = record_id;
        await idbPut('entities', entity);
    }

    window.dispatchEvent(new CustomEvent('store:change', {
        detail: { table, record_id, action, delta }
    }));
}

async function requestSync(tables) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const cursors = {};
    for (const table of tables) {
        const c = await idbGet('cursors', table);
        cursors[table] = c ? c.cursor : 0;
    }

    ws.send(JSON.stringify({ type: 'sync', cursors }));
}
"""
},

"outbox": {
    "order": 2, "lang": "javascript",
    "exports": "queueOp,processOutbox",
    "depends": "core",
    "content": r"""// ─── Offline-First Outbox ───
async function queueOp(operation) {
    await idbPut('outbox', {
        ...operation,
        status: 'pending',
        attempts: 0,
        created_at: Date.now()
    });

    if (navigator.onLine) processOutbox();
}

async function processOutbox() {
    const all = await idbGetAll('outbox');
    const pending = all.filter(op => op.status === 'pending');

    for (const op of pending) {
        if (op.attempts >= 3) {
            op.status = 'failed';
            await idbPut('outbox', op);
            continue;
        }

        try {
            const url = `${config.apiUrl}/${op.table}/${op.record_id || ''}`;
            const resp = await fetch(url, {
                method: op.action === 'delete' ? 'DELETE' : (op.record_id ? 'PUT' : 'POST'),
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: op.action !== 'delete' ? JSON.stringify(op.data) : undefined
            });

            if (resp.ok) {
                op.status = 'completed';
                await idbPut('outbox', op);
            } else {
                throw new Error(`HTTP ${resp.status}`);
            }
        } catch (e) {
            op.attempts++;
            op.last_error = e.message;
            await idbPut('outbox', op);
        }
    }
}

// Retry on reconnect
window.addEventListener('online', () => processOutbox());
setInterval(() => { if (navigator.onLine) processOutbox(); }, config.outboxRetry);
"""
},

"api": {
    "order": 3, "lang": "javascript",
    "exports": "default",
    "depends": "core,websocket,outbox",
    "content": r"""// ─── Public API ───
class MasStore {
    constructor() { this.listeners = new Map(); }

    async init(opts = {}) {
        Object.assign(config, opts);
        await openDB();
        if (opts.projectId) await connectWS(opts.projectId);
    }

    async get(table, id) {
        const key = `${table}:${id}`;
        return await idbGet('entities', key);
    }

    async save(table, entity) {
        if (!entity.id) entity.id = crypto.randomUUID();
        const key = `${table}:${entity.id}`;
        entity._table = table;
        entity._record_id = entity.id;
        Object.assign(entity, { id: key });
        await idbPut('entities', entity);

        await queueOp({ table, record_id: entity._record_id, action: 'save', data: entity });
        return entity;
    }

    async delete(table, id) {
        const key = `${table}:${id}`;
        await idbDelete('entities', key);
        await queueOp({ table, record_id: id, action: 'delete' });
    }

    async query(table, filter = {}) {
        const all = await idbGetAll('entities');
        return all.filter(e => {
            if (e._table !== table) return false;
            for (const [k, v] of Object.entries(filter)) {
                if (e[k] !== v) return false;
            }
            return true;
        });
    }

    async sync(tables) { await requestSync(tables); }

    on(event, cb) {
        if (!this.listeners.has(event)) this.listeners.set(event, []);
        this.listeners.get(event).push(cb);
        return () => { const cbs = this.listeners.get(event); cbs.splice(cbs.indexOf(cb), 1); };
    }
}

const masStore = new MasStore();

window.addEventListener('store:change', (e) => {
    const cbs = masStore.listeners.get('change') || [];
    cbs.forEach(cb => cb(e.detail));
});

window.masStore = masStore;
export default masStore;
"""
}
}


# ═══════════════════════════════════════════════════════
# MOBILE KIT
# ═══════════════════════════════════════════════════════

MOBILE_KIT_BULKS = {
"shell": {
    "order": 0, "lang": "javascript",
    "exports": "MobileShell",
    "depends": "",
    "content": r"""// Mobile Kit — Shell (Header + Footer + SideMenu)
function MobileShell(cfg) {
    const app_name = cfg.app_name || 'App';
    const logo = cfg.logo || '/assets/logo.png';
    const tabs = cfg.tabs || [
        { icon: 'home', label: 'Home', route: '/' },
        { icon: 'search', label: 'Search', route: '/search' },
        { icon: 'plus', label: 'Add', route: '/add', special: true },
        { icon: 'bell', label: 'Alerts', route: '/alerts' },
        { icon: 'user', label: 'Profile', route: '/profile' }
    ];
    const menuItems = cfg.menuItems || [];

    return {
        header: `
            <header class="m-header" data-theme="${cfg.theme || 'light'}">
                <button class="m-btn" onclick="MobileShell.toggleMenu()"><i class="icon-menu"></i></button>
                <div class="m-title">${cfg.showLogo ? `<img src="${logo}" alt="${app_name}">` : `<h1>${app_name}</h1>`}</div>
                <div class="m-actions">${(cfg.headerActions || []).map(a => `<button class="m-btn" data-action="${a.action}"><i class="icon-${a.icon}"></i>${a.badge ? `<span class="badge">${a.badge}</span>` : ''}</button>`).join('')}</div>
            </header>`,

        footer: `
            <nav class="m-footer">
                ${tabs.map(t => `
                    <button class="m-tab${t.special ? ' special' : ''}" data-route="${t.route}">
                        <i class="icon-${t.icon}"></i>
                        <span>${t.label}</span>
                    </button>
                `).join('')}
            </nav>`,

        sidemenu: `
            <aside class="m-menu" id="sideMenu">
                <div class="m-menu-overlay" onclick="MobileShell.toggleMenu()"></div>
                <div class="m-menu-panel">
                    <div class="m-menu-header">
                        <img src="${logo}" alt="${app_name}">
                        <button onclick="MobileShell.toggleMenu()"><i class="icon-x"></i></button>
                    </div>
                    <nav class="m-menu-nav">
                        ${menuItems.map(item => `
                            <a href="${item.route}" class="m-menu-item">
                                <i class="icon-${item.icon}"></i>
                                <span>${item.label}</span>
                                ${item.badge ? `<span class="badge">${item.badge}</span>` : ''}
                            </a>
                        `).join('')}
                    </nav>
                </div>
            </aside>`,

        // Render full shell
        render(content) {
            return `<!DOCTYPE html>
<html lang="${cfg.lang || 'en'}" dir="${cfg.rtl ? 'rtl' : 'ltr'}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>${app_name}</title>
    <link rel="stylesheet" href="/assets/mobile-kit.css">
    ${cfg.extraHead || ''}
</head>
<body class="mobile-app">
    ${this.header}
    ${this.sidemenu}
    <main class="m-content">${content}</main>
    ${this.footer}
    <script src="/lib/mas-store.js"></script>
    <script src="/lib/mas-core.js"></script>
    ${cfg.extraScripts || ''}
</body>
</html>`;
        }
    };
}

MobileShell.toggleMenu = function() {
    document.getElementById('sideMenu')?.classList.toggle('open');
};

MobileShell.navigate = function(route) {
    document.querySelectorAll('.m-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-route="${route}"]`)?.classList.add('active');
    if (window.router) window.router.push(route);
};

// Init tab navigation
document.addEventListener('click', (e) => {
    const tab = e.target.closest('.m-tab');
    if (tab) MobileShell.navigate(tab.dataset.route);
});
"""
},

"auth_screens": {
    "order": 1, "lang": "javascript",
    "exports": "AuthScreens",
    "depends": "shell",
    "content": r"""// Mobile Kit — Auth Screens (Login, Register, Reset, Splash)
const AuthScreens = {
    splash(cfg) {
        return `
        <div class="splash-screen" style="background:${cfg.bg || 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'}">
            <img src="${cfg.logo}" alt="${cfg.app_name}" class="splash-logo">
            <h1 class="splash-title">${cfg.app_name}</h1>
            ${cfg.tagline ? `<p class="splash-tagline">${cfg.tagline}</p>` : ''}
            <div class="splash-spinner"></div>
        </div>`;
    },

    login(cfg) {
        return `
        <div class="auth-page">
            <div class="auth-card">
                <img src="${cfg.logo}" alt="${cfg.app_name}" class="auth-logo">
                <h2>${cfg.loginTitle || 'Welcome Back'}</h2>
                <form id="loginForm" onsubmit="AuthScreens.handleLogin(event)">
                    <div class="input-group">
                        <i class="icon-user"></i>
                        <input type="text" name="username" placeholder="${cfg.userPlaceholder || 'Email or Phone'}" required>
                    </div>
                    <div class="input-group">
                        <i class="icon-lock"></i>
                        <input type="password" name="password" placeholder="Password" required>
                        <button type="button" class="toggle-pw" onclick="AuthScreens.togglePassword(this)">
                            <i class="icon-eye"></i>
                        </button>
                    </div>
                    <div class="auth-options">
                        <label><input type="checkbox" name="remember"> Remember me</label>
                        <a href="/reset-password">Forgot Password?</a>
                    </div>
                    <button type="submit" class="btn-primary btn-block">Sign In</button>
                </form>
                ${cfg.socialLogin ? `
                <div class="auth-divider"><span>OR</span></div>
                <div class="social-buttons">
                    <button class="btn-social google" onclick="AuthScreens.socialAuth('google')"><i class="icon-google"></i> Google</button>
                    <button class="btn-social apple" onclick="AuthScreens.socialAuth('apple')"><i class="icon-apple"></i> Apple</button>
                </div>` : ''}
                <p class="auth-footer">Don't have an account? <a href="/register">Sign Up</a></p>
            </div>
        </div>`;
    },

    register(cfg) {
        return `
        <div class="auth-page">
            <div class="auth-card">
                <img src="${cfg.logo}" alt="${cfg.app_name}" class="auth-logo">
                <h2>${cfg.registerTitle || 'Create Account'}</h2>
                <form id="registerForm" onsubmit="AuthScreens.handleRegister(event)">
                    <div class="input-group"><i class="icon-user"></i><input type="text" name="fullname" placeholder="Full Name" required></div>
                    <div class="input-group"><i class="icon-mail"></i><input type="email" name="email" placeholder="Email" required></div>
                    <div class="input-group"><i class="icon-phone"></i><input type="tel" name="phone" placeholder="Phone" required></div>
                    <div class="input-group"><i class="icon-lock"></i><input type="password" name="password" placeholder="Password" required></div>
                    <div class="input-group"><i class="icon-lock"></i><input type="password" name="confirm" placeholder="Confirm Password" required></div>
                    <label class="terms"><input type="checkbox" required> I agree to <a href="/terms">Terms</a></label>
                    <button type="submit" class="btn-primary btn-block">Create Account</button>
                </form>
                <p class="auth-footer">Already have an account? <a href="/login">Sign In</a></p>
            </div>
        </div>`;
    },

    resetPassword(cfg) {
        return `
        <div class="auth-page">
            <div class="auth-card">
                <h2>Reset Password</h2>
                <p class="auth-subtitle">Enter your email to receive a reset link</p>
                <form id="resetForm" onsubmit="AuthScreens.handleReset(event)">
                    <div class="input-group"><i class="icon-mail"></i><input type="email" name="email" placeholder="Email" required></div>
                    <button type="submit" class="btn-primary btn-block">Send Reset Link</button>
                </form>
                <p class="auth-footer"><a href="/login">Back to Login</a></p>
            </div>
        </div>`;
    },

    // Handlers
    async handleLogin(e) {
        e.preventDefault();
        const form = new FormData(e.target);
        const btn = e.target.querySelector('button[type=submit]');
        btn.disabled = true; btn.textContent = 'Signing in...';
        try {
            const resp = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: form.get('username'), password: form.get('password') })
            });
            const data = await resp.json();
            if (resp.ok && data.token) {
                localStorage.setItem('token', data.token);
                window.location.href = '/';
            } else {
                alert(data.error || 'Login failed');
            }
        } catch (err) { alert('Connection error'); }
        finally { btn.disabled = false; btn.textContent = 'Sign In'; }
    },

    async handleRegister(e) {
        e.preventDefault();
        const form = new FormData(e.target);
        if (form.get('password') !== form.get('confirm')) { alert('Passwords do not match'); return; }
        const resp = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fullname: form.get('fullname'), email: form.get('email'), phone: form.get('phone'), password: form.get('password') })
        });
        if (resp.ok) window.location.href = '/login?registered=1';
        else alert('Registration failed');
    },

    async handleReset(e) {
        e.preventDefault();
        const form = new FormData(e.target);
        await fetch('/api/auth/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: form.get('email') }) });
        alert('Reset link sent to your email');
    },

    togglePassword(btn) {
        const input = btn.previousElementSibling;
        input.type = input.type === 'password' ? 'text' : 'password';
    },

    socialAuth(provider) { window.location.href = `/api/auth/oauth/${provider}`; }
};
"""
},

"mobile_css": {
    "order": 2, "lang": "css",
    "exports": "",
    "depends": "",
    "content": r"""/* Mobile Kit CSS */
:root{--primary:#2196F3;--secondary:#FF9800;--success:#4CAF50;--danger:#F44336;--dark:#212121;--gray:#9E9E9E;--light:#F5F5F5;--header-h:56px;--footer-h:56px;--menu-w:280px;--radius:8px;--shadow:0 2px 8px rgba(0,0,0,.1)}
*{box-sizing:border-box;margin:0;padding:0}
body.mobile-app{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--light);min-height:100vh;overflow-x:hidden}
.m-header{position:fixed;top:0;left:0;right:0;height:var(--header-h);background:#fff;box-shadow:var(--shadow);display:flex;align-items:center;padding:0 12px;z-index:100}
.m-header .m-title{flex:1;text-align:center}.m-header .m-title h1{font-size:18px;font-weight:600}.m-header .m-title img{height:32px}
.m-btn{width:40px;height:40px;border:none;background:transparent;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;position:relative}
.m-btn .badge{position:absolute;top:4px;right:4px;background:var(--danger);color:#fff;font-size:10px;padding:1px 4px;border-radius:8px}
.m-content{padding:calc(var(--header-h) + 8px) 16px calc(var(--footer-h) + 8px)}
.m-footer{position:fixed;bottom:0;left:0;right:0;height:var(--footer-h);background:#fff;box-shadow:0 -2px 8px rgba(0,0,0,.05);display:flex;z-index:100}
.m-tab{flex:1;border:none;background:transparent;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;color:var(--gray);font-size:10px;cursor:pointer;transition:.2s}
.m-tab.active,.m-tab:hover{color:var(--primary)}.m-tab.special{color:var(--primary);font-size:24px}
.m-menu{position:fixed;inset:0;z-index:200;pointer-events:none;transition:.3s}
.m-menu.open{pointer-events:all}
.m-menu-overlay{position:absolute;inset:0;background:rgba(0,0,0,.5);opacity:0;transition:.3s}
.m-menu.open .m-menu-overlay{opacity:1}
.m-menu-panel{position:absolute;top:0;bottom:0;left:0;width:var(--menu-w);background:#fff;transform:translateX(-100%);transition:.3s;display:flex;flex-direction:column}
.m-menu.open .m-menu-panel{transform:translateX(0)}
.m-menu-header{padding:20px;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:space-between}
.m-menu-header img{height:32px}
.m-menu-header button{color:#fff;background:transparent;border:none;cursor:pointer}
.m-menu-nav{flex:1;overflow-y:auto;padding:8px 0}
.m-menu-item{display:flex;align-items:center;gap:12px;padding:12px 20px;color:var(--dark);text-decoration:none;transition:.2s}
.m-menu-item:hover{background:rgba(0,0,0,.03)}
/* Auth */
.auth-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;background:linear-gradient(135deg,var(--primary),var(--secondary))}
.auth-card{background:#fff;padding:32px;border-radius:16px;width:100%;max-width:400px;box-shadow:0 10px 40px rgba(0,0,0,.1)}
.auth-card h2{text-align:center;margin-bottom:8px}.auth-logo{display:block;margin:0 auto 24px;height:48px}
.input-group{position:relative;margin-bottom:16px}.input-group input{width:100%;padding:12px 12px 12px 44px;border:1px solid #e0e0e0;border-radius:var(--radius);font-size:14px}
.input-group i{position:absolute;left:16px;top:50%;transform:translateY(-50%);color:var(--gray)}
.toggle-pw{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:transparent;border:none;cursor:pointer;color:var(--gray)}
.btn-primary{background:var(--primary);color:#fff;border:none;padding:12px 24px;border-radius:var(--radius);font-size:14px;font-weight:600;cursor:pointer;transition:.2s}
.btn-primary:hover{opacity:.9}.btn-block{width:100%}
.auth-options{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;font-size:13px}
.auth-divider{text-align:center;margin:20px 0;position:relative}.auth-divider::before{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:#e0e0e0}.auth-divider span{background:#fff;padding:0 12px;position:relative;color:var(--gray)}
.social-buttons{display:flex;gap:12px}.btn-social{flex:1;padding:10px;border:1px solid #e0e0e0;border-radius:var(--radius);background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px}
.auth-footer{text-align:center;margin-top:20px;font-size:14px;color:var(--gray)}.auth-footer a{color:var(--primary);font-weight:600;text-decoration:none}
/* Splash */
.splash-screen{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff}
.splash-logo{height:80px;margin-bottom:20px}.splash-title{font-size:28px;font-weight:700;margin-bottom:8px}
.splash-tagline{opacity:.8;font-size:16px}.splash-spinner{width:24px;height:24px;border:3px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;margin-top:40px;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
"""
}
}


# ═══════════════════════════════════════════════════════
# DASHBOARD KIT
# ═══════════════════════════════════════════════════════

DASHBOARD_KIT_BULKS = {
"layout": {
    "order": 0, "lang": "javascript",
    "exports": "DashboardLayout",
    "depends": "",
    "content": r"""// Dashboard Kit — Layout (Sidebar + Header + Content)
function DashboardLayout(cfg) {
    const { app_name, logo, menuItems, user, theme } = cfg;

    return {
        render(pageTitle, content) {
            return `<!DOCTYPE html>
<html data-theme="${theme || 'light'}">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>${pageTitle} — ${app_name}</title>
    <link rel="stylesheet" href="/assets/dashboard-kit.css">
</head>
<body class="dashboard">
    <aside class="d-sidebar" id="sidebar">
        <div class="d-sidebar-header">
            <img src="${logo}" alt="${app_name}">
            <button class="d-sidebar-toggle" onclick="DashboardLayout.toggleSidebar()"><i class="icon-menu"></i></button>
        </div>
        <nav class="d-sidebar-nav">
            ${(menuItems || []).map(group => `
                ${group.title ? `<h4 class="d-nav-group">${group.title}</h4>` : ''}
                ${(group.items || []).map(item => `
                    <a href="${item.route}" class="d-nav-item${item.active ? ' active' : ''}">
                        <i class="icon-${item.icon}"></i>
                        <span>${item.label}</span>
                        ${item.badge ? `<span class="d-badge">${item.badge}</span>` : ''}
                    </a>
                `).join('')}
            `).join('')}
        </nav>
        <div class="d-sidebar-footer">
            <div class="d-user">
                <img src="${user?.avatar || '/assets/avatar.png'}" class="d-avatar">
                <div><strong>${user?.name || 'Admin'}</strong><small>${user?.role || 'Administrator'}</small></div>
            </div>
        </div>
    </aside>
    <div class="d-main">
        <header class="d-header">
            <h1>${pageTitle}</h1>
            <div class="d-header-actions">
                <div class="d-search"><input type="text" placeholder="Search..."><i class="icon-search"></i></div>
                <button class="d-btn-icon" onclick="DashboardLayout.toggleTheme()"><i class="icon-${theme === 'dark' ? 'sun' : 'moon'}"></i></button>
                <button class="d-btn-icon"><i class="icon-bell"></i></button>
            </div>
        </header>
        <main class="d-content">${content}</main>
    </div>
</body>
</html>`;
        }
    };
}

DashboardLayout.toggleSidebar = () => document.getElementById('sidebar')?.classList.toggle('collapsed');
DashboardLayout.toggleTheme = () => {
    const html = document.documentElement;
    html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', html.dataset.theme);
};
"""
},

"widgets": {
    "order": 1, "lang": "javascript",
    "exports": "StatsCard,DataTable,ChartWidget",
    "depends": "layout",
    "content": r"""// Dashboard Kit — Widgets (StatsCard, DataTable, Chart)
function StatsCard({ label, value, icon, color, change }) {
    const changeClass = change > 0 ? 'positive' : change < 0 ? 'negative' : '';
    return `
    <div class="d-stats-card" style="--card-color:${color || 'var(--primary)'}">
        <div class="d-stats-icon"><i class="icon-${icon}"></i></div>
        <div class="d-stats-body">
            <h3>${typeof value === 'number' ? value.toLocaleString() : value}</h3>
            <p>${label}</p>
            ${change !== undefined ? `<span class="d-stats-change ${changeClass}">${change > 0 ? '+' : ''}${change}%</span>` : ''}
        </div>
    </div>`;
}

function DataTable({ title, columns, data, pageSize = 10 }) {
    let currentPage = 1;
    const totalPages = Math.ceil(data.length / pageSize);
    const paginated = data.slice((currentPage-1)*pageSize, currentPage*pageSize);

    return `
    <div class="d-table-widget">
        <div class="d-table-header">
            <h3>${title}</h3>
            <div class="d-table-actions">
                <input type="text" placeholder="Search..." class="d-table-search">
                <button class="d-btn-sm">Export</button>
            </div>
        </div>
        <table class="d-table">
            <thead><tr>${columns.map(c => `<th>${c.label}</th>`).join('')}</tr></thead>
            <tbody>${paginated.map(row => `<tr>${columns.map(c => `<td>${row[c.key] || ''}</td>`).join('')}</tr>`).join('')}</tbody>
        </table>
        <div class="d-table-footer">
            <span>Showing ${(currentPage-1)*pageSize+1}-${Math.min(currentPage*pageSize, data.length)} of ${data.length}</span>
            <div class="d-pagination">
                ${Array.from({length: totalPages}, (_, i) => `<button class="${i+1===currentPage?'active':''}">${i+1}</button>`).join('')}
            </div>
        </div>
    </div>`;
}

function ChartWidget({ title, type, data, height }) {
    return `
    <div class="d-chart-widget">
        <h3>${title}</h3>
        <div class="d-chart" style="height:${height || 250}px" data-type="${type}" data-values='${JSON.stringify(data)}'></div>
    </div>`;
}
"""
}
}


# ═══════════════════════════════════════════════════════
# PIPELINE SYSTEM
# ═══════════════════════════════════════════════════════

PIPELINE_BULK = {
    "order": 0, "lang": "javascript",
    "exports": "PipelineEngine",
    "depends": "",
    "content": r"""// Pipeline Engine — Orchestrates app building
class PipelineEngine {
    constructor() {
        this.pipelines = new Map();
        this.jobs = [];
    }

    register(name, stages) {
        this.pipelines.set(name, { name, stages, created: Date.now() });
    }

    async execute(pipelineName, context = {}) {
        const pipeline = this.pipelines.get(pipelineName);
        if (!pipeline) throw new Error(`Pipeline '${pipelineName}' not found`);

        const job = {
            id: `job_${Date.now()}_${Math.random().toString(36).slice(2,8)}`,
            pipeline: pipelineName,
            status: 'running',
            context,
            stages: {},
            startTime: Date.now()
        };
        this.jobs.push(job);

        for (const stage of pipeline.stages) {
            job.stages[stage.name] = { status: 'running', startTime: Date.now() };
            try {
                const result = await stage.handler(context);
                if (result) Object.assign(context, result);
                job.stages[stage.name].status = 'completed';
                job.stages[stage.name].duration = Date.now() - job.stages[stage.name].startTime;
            } catch (error) {
                job.stages[stage.name].status = 'failed';
                job.stages[stage.name].error = error.message;
                job.status = 'failed';
                job.error = error.message;
                throw error;
            }
        }

        job.status = 'completed';
        job.duration = Date.now() - job.startTime;
        return job;
    }

    getJob(id) { return this.jobs.find(j => j.id === id); }
    getHistory() { return this.jobs.slice(-50); }
}

// Pre-built pipelines
const pipelineEngine = new PipelineEngine();

// Mobile App Builder Pipeline
pipelineEngine.register('build-mobile-app', [
    { name: 'validate', handler: async (ctx) => {
        if (!ctx.app_name) throw new Error('app_name required');
        if (!ctx.kit_type) throw new Error('kit_type required');
        return { validated: true };
    }},
    { name: 'select-template', handler: async (ctx) => {
        return { template_id: ctx.template || 'default' };
    }},
    { name: 'generate-code', handler: async (ctx) => {
        // Generate from kit + variables
        return { code_generated: true, files_count: 12 };
    }},
    { name: 'configure-platform', handler: async (ctx) => {
        const configs = {};
        if (ctx.platforms?.includes('android')) configs.android = { package: `com.${ctx.app_id}`, minSdk: 21 };
        if (ctx.platforms?.includes('ios')) configs.ios = { bundle: `com.${ctx.app_id}`, target: '13.0' };
        return { platform_configs: configs };
    }},
    { name: 'build', handler: async (ctx) => {
        return { build_path: `/builds/${ctx.app_id}`, size: '12MB' };
    }},
    { name: 'sign', handler: async (ctx) => {
        return { signed: true };
    }},
    { name: 'deploy', handler: async (ctx) => {
        return { deployed: true, url: `https://${ctx.app_id}.app` };
    }}
]);

// Customer Onboarding Pipeline
pipelineEngine.register('customer-onboarding', [
    { name: 'create-account', handler: async (ctx) => {
        return { account_id: `acc_${Date.now()}` };
    }},
    { name: 'provision-workspace', handler: async (ctx) => {
        return { workspace_id: `ws_${Date.now()}`, subdomain: ctx.subdomain };
    }},
    { name: 'setup-billing', handler: async (ctx) => {
        return { billing_status: 'trial', trial_ends: new Date(Date.now() + 14*24*60*60*1000) };
    }},
    { name: 'create-apps', handler: async (ctx) => {
        return { apps_created: ctx.app_types?.length || 1 };
    }},
    { name: 'notify', handler: async (ctx) => {
        return { notifications_sent: true };
    }}
]);
"""
}


async def main():
    print("=" * 70)
    print("QDML Complete System Registration")
    print("=" * 70)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"})
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ════════════════════════════════════
    # 1. mas-store unified
    # ════════════════════════════════════
    print("\n[1/5] mas-store unified...")
    try:
        await engine.create_module("mas-front", "Shared Libraries", "shared", tier="frontend", app="shared")
    except: pass
    try:
        await engine.create_component("shared", "MAS Store Unified", "mas-store", kind="library", target="mas-js", project_slug="mas-front")
    except: pass

    for name, data in MAS_STORE_BULKS.items():
        await engine.create_bulk("mas-store", name, data["content"], lang=data["lang"],
            bulk_order=data["order"], depends=data.get("depends",""), exports=data.get("exports",""), project_slug="mas-front")
    print(f"       {len(MAS_STORE_BULKS)} bulks registered")

    # ════════════════════════════════════
    # 2. Kit System project
    # ════════════════════════════════════
    print("\n[2/5] Kit System...")
    try:
        await engine.create_project("Kit System", "kits", "Mobile, Dashboard, Offer templates")
    except: pass

    # Mobile Kit
    try:
        await engine.create_module("kits", "Mobile Kit", "mobile-kit", tier="frontend", app="kits")
    except: pass
    try:
        await engine.create_component("mobile-kit", "Mobile Kit Components", "mobile-kit-components", kind="library", target="mas-js", project_slug="kits")
    except: pass

    for name, data in MOBILE_KIT_BULKS.items():
        await engine.create_bulk("mobile-kit-components", name, data["content"], lang=data["lang"],
            bulk_order=data["order"], depends=data.get("depends",""), exports=data.get("exports",""), project_slug="kits")
    print(f"       Mobile Kit: {len(MOBILE_KIT_BULKS)} bulks")

    # Dashboard Kit
    try:
        await engine.create_module("kits", "Dashboard Kit", "dashboard-kit", tier="frontend", app="kits")
    except: pass
    try:
        await engine.create_component("dashboard-kit", "Dashboard Kit Components", "dashboard-kit-components", kind="library", target="mas-js", project_slug="kits")
    except: pass

    for name, data in DASHBOARD_KIT_BULKS.items():
        await engine.create_bulk("dashboard-kit-components", name, data["content"], lang=data["lang"],
            bulk_order=data["order"], depends=data.get("depends",""), exports=data.get("exports",""), project_slug="kits")
    print(f"       Dashboard Kit: {len(DASHBOARD_KIT_BULKS)} bulks")

    # Pipeline
    try:
        await engine.create_module("kits", "Pipeline System", "pipeline", tier="backend", app="pipeline")
    except: pass
    try:
        await engine.create_component("pipeline", "Pipeline Engine", "pipeline-engine", kind="service", target="node", project_slug="kits")
    except: pass

    await engine.create_bulk("pipeline-engine", "main", PIPELINE_BULK["content"], lang="javascript",
        bulk_order=0, exports=PIPELINE_BULK["exports"], project_slug="kits")
    print(f"       Pipeline: 1 bulk")

    # ════════════════════════════════════
    # 3. Kit Registry entries
    # ════════════════════════════════════
    print("\n[3/5] Registering kits in registry...")

    async with pool.acquire() as conn:
        kits = [
            ('mobile', 'Mobile App Kit', 'mobile-kit', '{"shell":true,"auth":true,"tabs":true,"sidemenu":true}', '["shell","auth_screens","mobile_css"]', '{"app_name":"","logo":"","primary_color":"#2196F3","tabs":[],"menuItems":[]}'),
            ('dashboard', 'Dashboard Kit', 'dashboard-kit', '{"sidebar":true,"header":true,"widgets":true}', '["layout","widgets"]', '{"app_name":"","logo":"","menuItems":[],"theme":"light"}'),
            ('offer', 'Offer/Pricing Kit', 'offer-kit', '{"pricing":true,"features":true,"cta":true}', '[]', '{"plans":[],"currency":"USD","features":[]}'),
        ]

        for kit_type, name, slug, config, components, variables in kits:
            await conn.execute(f"""
                INSERT INTO {QDML_SCHEMA}.kit_registry (kit_type, name, slug, config, components, variables)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb)
                ON CONFLICT (slug) DO UPDATE SET config=$4::jsonb, components=$5::jsonb, variables=$6::jsonb
            """, kit_type, name, slug, config, components, variables)
            print(f"       Kit: {slug}")

    # ════════════════════════════════════
    # 4. Pipeline definitions in DB
    # ════════════════════════════════════
    print("\n[4/5] Registering pipelines...")

    async with pool.acquire() as conn:
        pipelines = [
            ('build-mobile-app', 'App Builder', 'build', '["validate","select-template","generate-code","configure-platform","build","sign","deploy"]', '{"timeout":300000,"retry":3}'),
            ('customer-onboarding', 'Customer Onboarding', 'onboarding', '["create-account","provision-workspace","setup-billing","create-apps","notify"]', '{"timeout":60000}'),
            ('app-update', 'App Update', 'update', '["validate","pull-changes","build","test","deploy"]', '{"timeout":180000}'),
        ]

        for slug, name, ptype, stages, config in pipelines:
            await conn.execute(f"""
                INSERT INTO {QDML_SCHEMA}.pipelines (name, slug, type, stages, config)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
                ON CONFLICT (slug) DO UPDATE SET stages=$4::jsonb, config=$5::jsonb
            """, name, slug, ptype, stages, config)
            print(f"       Pipeline: {slug}")

    # ════════════════════════════════════
    # 5. Compile all new components
    # ════════════════════════════════════
    print("\n[5/5] Compiling new components...")

    gen_base = Path("/srv/apps/ai-first/mas-front/_generated")

    compilations = [
        ("mas-store", "mas-front", gen_base / "shared" / "mas-store.js"),
        ("mobile-kit-components", "kits", gen_base / "kits" / "mobile-kit.js"),
        ("dashboard-kit-components", "kits", gen_base / "kits" / "dashboard-kit.js"),
        ("pipeline-engine", "kits", gen_base / "kits" / "pipeline-engine.js"),
    ]

    for comp_slug, proj_slug, output_path in compilations:
        code = await engine.compile_component(comp_slug, project_slug=proj_slug)
        if code:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(code, encoding="utf-8")
            print(f"       {comp_slug}: {code.count(chr(10))+1} lines -> {output_path.name}")

    # ════════════════════════════════════
    # Final Stats
    # ════════════════════════════════════
    stats = await engine.stats()
    print(f"\n{'=' * 70}")
    print(f"SYSTEM TOTALS:")
    print(f"  Projects:   {stats['projects']}")
    print(f"  Modules:    {stats['modules']}")
    print(f"  Components: {stats['components']}")
    print(f"  Bulks:      {stats['bulks']}")
    print(f"  Lines:      {stats['total_lines']:,}")
    print(f"  DB Size:    {stats['db_size_mb']} MB")
    print(f"{'=' * 70}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
