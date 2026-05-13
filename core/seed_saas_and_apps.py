#!/usr/bin/env python3
"""
Seed MAS-SAAS Platform Dashboard + Mostamal Hawaa App
"""
import asyncio
import asyncpg
from pathlib import Path
from qdml_engine import QDMLEngine
from config import DATABASE_URL, QDML_SCHEMA


SAAS_DASHBOARD_BULKS = {
"saas_layout": {
    "order": 0, "lang": "javascript",
    "exports": "SaasDashboard",
    "content": r"""// MAS-SAAS Developer Dashboard
const SaasDashboard = {
    layout(cfg) {
        return `<!DOCTYPE html>
<html data-theme="${cfg.theme||'light'}"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${cfg.pageTitle} — MAS-SAAS</title>
<link rel="stylesheet" href="/assets/dashboard-kit.css">
<link rel="stylesheet" href="/assets/saas.css">
</head><body class="dashboard">
<aside class="d-sidebar" id="sidebar">
    <div class="d-sidebar-header"><img src="/assets/mas-saas-logo.svg" alt="MAS-SAAS"><span class="brand">MAS-SAAS</span></div>
    <nav class="d-sidebar-nav">
        <h4 class="d-nav-group">Main</h4>
        <a href="/saas" class="d-nav-item ${cfg.page==='home'?'active':''}"><i class="icon-dashboard"></i><span>Dashboard</span></a>
        <a href="/saas/customers" class="d-nav-item ${cfg.page==='customers'?'active':''}"><i class="icon-users"></i><span>Customers</span></a>
        <a href="/saas/apps" class="d-nav-item ${cfg.page==='apps'?'active':''}"><i class="icon-box"></i><span>Applications</span></a>
        <a href="/saas/pipeline" class="d-nav-item ${cfg.page==='pipeline'?'active':''}"><i class="icon-git-branch"></i><span>Pipeline</span></a>

        <h4 class="d-nav-group">Build</h4>
        <a href="/saas/kits" class="d-nav-item ${cfg.page==='kits'?'active':''}"><i class="icon-package"></i><span>Kits</span></a>
        <a href="/saas/templates" class="d-nav-item ${cfg.page==='templates'?'active':''}"><i class="icon-layout"></i><span>Templates</span></a>
        <a href="/saas/deploy" class="d-nav-item ${cfg.page==='deploy'?'active':''}"><i class="icon-upload"></i><span>Deploy</span></a>

        <h4 class="d-nav-group">System</h4>
        <a href="/saas/billing" class="d-nav-item ${cfg.page==='billing'?'active':''}"><i class="icon-credit-card"></i><span>Billing</span></a>
        <a href="/saas/settings" class="d-nav-item ${cfg.page==='settings'?'active':''}"><i class="icon-settings"></i><span>Settings</span></a>
        <a href="/saas/logs" class="d-nav-item ${cfg.page==='logs'?'active':''}"><i class="icon-activity"></i><span>Logs</span></a>
    </nav>
</aside>
<div class="d-main">
    <header class="d-header">
        <div class="d-header-left"><h1>${cfg.pageTitle}</h1></div>
        <div class="d-header-actions">
            <button class="d-btn-sm" onclick="location.href='/saas/apps/new'"><i class="icon-plus"></i> New App</button>
            <button class="d-btn-icon"><i class="icon-bell"></i><span class="d-badge">3</span></button>
        </div>
    </header>
    <main class="d-content">${cfg.content}</main>
</div>
</body></html>`;
    },

    // Dashboard home page
    homePage(stats) {
        return `
        <div class="d-grid-4">
            ${StatsCard({label:'Total Customers', value:stats.customers, icon:'users', color:'#2196F3', change:12})}
            ${StatsCard({label:'Active Apps', value:stats.apps, icon:'box', color:'#4CAF50', change:8})}
            ${StatsCard({label:'Monthly Revenue', value:'$'+stats.revenue, icon:'dollar-sign', color:'#FF9800', change:15})}
            ${StatsCard({label:'Pipeline Jobs', value:stats.pipeline_jobs, icon:'git-branch', color:'#9C27B0', change:-3})}
        </div>

        <div class="d-grid-2" style="margin-top:24px">
            <div class="d-card">
                <h3>Recent Activity</h3>
                <div class="activity-feed">
                    ${(stats.recent_activity||[]).map(a => `
                        <div class="activity-item">
                            <span class="activity-icon"><i class="icon-${a.icon}"></i></span>
                            <div class="activity-content"><strong>${a.title}</strong><p>${a.description}</p></div>
                            <small>${a.time}</small>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="d-card">
                <h3>App Status</h3>
                <div class="status-list">
                    ${(stats.app_statuses||[]).map(app => `
                        <div class="status-item">
                            <span class="status-dot status-${app.status}"></span>
                            <span class="status-name">${app.name}</span>
                            <span class="status-label">${app.status}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>`;
    }
};

function StatsCard({label, value, icon, color, change}) {
    return `<div class="d-stats-card" style="--card-color:${color}"><div class="d-stats-icon"><i class="icon-${icon}"></i></div><div class="d-stats-body"><h3>${value}</h3><p>${label}</p>${change?`<span class="d-stats-change ${change>0?'positive':'negative'}">${change>0?'+':''}${change}%</span>`:''}</div></div>`;
}
"""
},

"saas_pipeline_page": {
    "order": 1, "lang": "javascript",
    "exports": "PipelinePage",
    "content": r"""// MAS-SAAS Pipeline Management Page
const PipelinePage = {
    render(pipelines, jobs) {
        return `
        <div class="pipeline-header">
            <div class="pipeline-tabs">
                <button class="tab active" data-tab="active">Active Jobs</button>
                <button class="tab" data-tab="history">History</button>
                <button class="tab" data-tab="config">Configuration</button>
            </div>
            <button class="d-btn-sm" onclick="PipelinePage.newJob()"><i class="icon-play"></i> Run Pipeline</button>
        </div>

        <div class="pipeline-board" id="pipelineBoard">
            <div class="pipeline-column">
                <h4><span class="col-dot draft"></span> Draft</h4>
                ${jobs.filter(j=>j.status==='draft').map(j => PipelinePage.jobCard(j)).join('')}
            </div>
            <div class="pipeline-column">
                <h4><span class="col-dot building"></span> Building</h4>
                ${jobs.filter(j=>j.status==='building').map(j => PipelinePage.jobCard(j)).join('')}
            </div>
            <div class="pipeline-column">
                <h4><span class="col-dot testing"></span> Testing</h4>
                ${jobs.filter(j=>j.status==='testing').map(j => PipelinePage.jobCard(j)).join('')}
            </div>
            <div class="pipeline-column">
                <h4><span class="col-dot ready"></span> Ready</h4>
                ${jobs.filter(j=>j.status==='ready').map(j => PipelinePage.jobCard(j)).join('')}
            </div>
            <div class="pipeline-column">
                <h4><span class="col-dot published"></span> Published</h4>
                ${jobs.filter(j=>j.status==='published').map(j => PipelinePage.jobCard(j)).join('')}
            </div>
        </div>

        <div class="pipeline-configs" style="margin-top:32px">
            <h3>Pipeline Configurations</h3>
            <div class="d-grid-3">
                ${pipelines.map(p => `
                    <div class="d-card pipeline-config-card">
                        <h4>${p.name}</h4>
                        <p>Type: ${p.type}</p>
                        <p>Stages: ${JSON.parse(p.stages).length}</p>
                        <div class="card-actions">
                            <button class="d-btn-sm" onclick="PipelinePage.runPipeline('${p.slug}')">Run</button>
                            <button class="d-btn-sm secondary" onclick="PipelinePage.editPipeline('${p.slug}')">Edit</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>`;
    },

    jobCard(job) {
        return `
        <div class="pipeline-card" data-id="${job.id}">
            <div class="pipeline-card-header">
                <strong>${job.app_name}</strong>
                <span class="pipeline-badge ${job.status}">${job.status}</span>
            </div>
            <div class="pipeline-card-body">
                <small>Platform: ${job.platform || 'all'}</small>
                <div class="pipeline-progress">
                    <div class="progress-bar" style="width:${job.progress||0}%"></div>
                </div>
            </div>
            <div class="pipeline-card-footer">
                <small>${job.started || 'Not started'}</small>
                <div class="pipeline-actions">
                    <button class="btn-icon" title="View"><i class="icon-eye"></i></button>
                    <button class="btn-icon" title="Cancel"><i class="icon-x"></i></button>
                </div>
            </div>
        </div>`;
    },

    async newJob() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `<div class="modal"><h3>New Pipeline Job</h3>
            <form onsubmit="PipelinePage.submitJob(event)">
                <select name="pipeline" required><option value="">Select Pipeline</option><option value="build-mobile-app">Build Mobile App</option><option value="customer-onboarding">Customer Onboarding</option></select>
                <input name="app_name" placeholder="App Name" required>
                <select name="platform"><option value="android">Android</option><option value="ios">iOS</option><option value="both">Both</option></select>
                <button type="submit" class="d-btn-sm">Start</button>
                <button type="button" class="d-btn-sm secondary" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
            </form></div>`;
        document.body.appendChild(modal);
    },

    async submitJob(e) {
        e.preventDefault();
        const form = new FormData(e.target);
        const resp = await fetch(`/api/kits/pipelines/${form.get('pipeline')}/execute`, {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({app_name: form.get('app_name'), platforms: [form.get('platform')]})
        });
        if (resp.ok) { location.reload(); }
    },

    async runPipeline(slug) { /* trigger pipeline */ },
    async editPipeline(slug) { /* open editor */ }
};
"""
},

"saas_customers_page": {
    "order": 2, "lang": "javascript",
    "exports": "CustomersPage",
    "content": r"""// MAS-SAAS Customer Management
const CustomersPage = {
    render(customers) {
        return `
        <div class="page-actions">
            <div class="search-bar"><input type="text" placeholder="Search customers..." oninput="CustomersPage.search(this.value)"><i class="icon-search"></i></div>
            <button class="d-btn-sm" onclick="CustomersPage.addCustomer()"><i class="icon-plus"></i> Add Customer</button>
        </div>

        <div class="d-card" style="margin-top:16px">
            <table class="d-table">
                <thead><tr><th>Customer</th><th>Plan</th><th>Apps</th><th>Status</th><th>MRR</th><th>Actions</th></tr></thead>
                <tbody>
                    ${customers.map(c => `
                    <tr>
                        <td><div class="customer-cell"><img src="${c.avatar||'/assets/avatar.png'}" class="d-avatar-sm"><div><strong>${c.name}</strong><small>${c.email}</small></div></div></td>
                        <td><span class="plan-badge ${c.plan}">${c.plan}</span></td>
                        <td>${c.apps_count}</td>
                        <td><span class="status-dot status-${c.status}"></span> ${c.status}</td>
                        <td>$${c.mrr}</td>
                        <td>
                            <button class="btn-icon" title="View" onclick="CustomersPage.view('${c.id}')"><i class="icon-eye"></i></button>
                            <button class="btn-icon" title="Apps" onclick="CustomersPage.manageApps('${c.id}')"><i class="icon-box"></i></button>
                            <button class="btn-icon" title="Edit" onclick="CustomersPage.edit('${c.id}')"><i class="icon-edit"></i></button>
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
    },

    search(query) { /* filter table */ },
    addCustomer() { /* modal */ },
    view(id) { location.href = `/saas/customers/${id}`; },
    manageApps(id) { location.href = `/saas/customers/${id}/apps`; },
    edit(id) { /* modal */ }
};
"""
}
}

MOSTAMAL_HAWAA_BULKS = {
"app_shell": {
    "order": 0, "lang": "javascript",
    "exports": "MostamalApp",
    "content": r"""// Mostamal Hawaa — Complete Mobile App Shell
const MostamalApp = {
    config: {
        app_name: 'مستعمل حواء',
        app_name_en: 'Mostamal Hawaa',
        logo: '/assets/mostamal-logo.png',
        primary_color: '#E91E63',
        secondary_color: '#FFC107',
        lang: 'ar',
        rtl: true,
        currency: 'SAR',
        country: 'SA'
    },

    tabs: [
        { icon: 'home', label: 'الرئيسية', route: '/' },
        { icon: 'grid', label: 'الأقسام', route: '/categories' },
        { icon: 'plus-circle', label: 'أضف إعلان', route: '/add', special: true },
        { icon: 'message-circle', label: 'المحادثات', route: '/chat' },
        { icon: 'user', label: 'حسابي', route: '/profile' }
    ],

    menuItems: [
        { icon: 'home', label: 'الرئيسية', route: '/' },
        { icon: 'grid', label: 'جميع الأقسام', route: '/categories' },
        { icon: 'list', label: 'إعلاناتي', route: '/my-ads' },
        { icon: 'heart', label: 'المفضلة', route: '/favorites' },
        { icon: 'clock', label: 'آخر المشاهدات', route: '/recent' },
        { icon: 'bell', label: 'الإشعارات', route: '/notifications' },
        { icon: 'help-circle', label: 'المساعدة', route: '/help' },
        { icon: 'settings', label: 'الإعدادات', route: '/settings' }
    ],

    init() {
        // Initialize mas-store
        if (window.masStore) {
            masStore.init({
                projectId: 'mostamal-hawaa',
                wsUrl: 'ws://localhost:8003'
            });
        }

        // Register routes
        this.router = new MobileRouter();
        this.router.register('/', () => this.pages.home());
        this.router.register('/categories', () => this.pages.categories());
        this.router.register('/categories/:id', (p) => this.pages.categoryDetail(p.id));
        this.router.register('/product/:id', (p) => this.pages.productDetail(p.id));
        this.router.register('/add', () => this.pages.addProduct());
        this.router.register('/chat', () => this.pages.chatList());
        this.router.register('/chat/:id', (p) => this.pages.chatDetail(p.id));
        this.router.register('/profile', () => this.pages.profile());
        this.router.register('/my-ads', () => this.pages.myAds());
        this.router.register('/favorites', () => this.pages.favorites());
        this.router.register('/login', () => this.pages.login());
        this.router.register('/register', () => this.pages.register());

        this.render();
    },

    render() {
        const shell = MobileShell({
            ...this.config,
            tabs: this.tabs,
            menuItems: this.menuItems,
            showLogo: true,
            headerActions: [
                { icon: 'search', action: 'search' },
                { icon: 'bell', action: 'notifications', badge: 3 }
            ]
        });

        document.getElementById('app').innerHTML = shell.render(
            '<div id="page-content"></div>'
        );

        // Navigate to current route
        this.router.navigate(window.location.pathname);
    },

    pages: {
        home() {
            return `
            <div class="mostamal-home">
                <div class="search-hero">
                    <input type="text" placeholder="ابحث في مستعمل حواء..." class="search-input">
                    <button class="search-btn"><i class="icon-search"></i></button>
                </div>

                <div class="categories-grid">
                    <a href="/categories/fashion" class="cat-item"><i class="icon-shopping-bag"></i><span>أزياء</span></a>
                    <a href="/categories/beauty" class="cat-item"><i class="icon-star"></i><span>تجميل</span></a>
                    <a href="/categories/kids" class="cat-item"><i class="icon-heart"></i><span>أطفال</span></a>
                    <a href="/categories/home" class="cat-item"><i class="icon-home"></i><span>منزل</span></a>
                    <a href="/categories/electronics" class="cat-item"><i class="icon-smartphone"></i><span>إلكترونيات</span></a>
                    <a href="/categories/sports" class="cat-item"><i class="icon-activity"></i><span>رياضة</span></a>
                </div>

                <h2 class="section-title">أحدث الإعلانات</h2>
                <div class="products-grid" id="latestProducts">
                    <!-- Products loaded dynamically -->
                </div>
            </div>`;
        },

        categories() { return '<div class="categories-page"><h2>جميع الأقسام</h2></div>'; },
        categoryDetail(id) { return `<div class="category-detail"><h2>قسم: ${id}</h2></div>`; },
        productDetail(id) { return `<div class="product-detail"><h2>المنتج: ${id}</h2></div>`; },
        addProduct() { return '<div class="add-product"><h2>أضف إعلان جديد</h2></div>'; },
        chatList() { return '<div class="chat-list"><h2>المحادثات</h2></div>'; },
        chatDetail(id) { return `<div class="chat-detail"><h2>محادثة: ${id}</h2></div>`; },
        profile() { return '<div class="profile-page"><h2>حسابي</h2></div>'; },
        myAds() { return '<div class="my-ads"><h2>إعلاناتي</h2></div>'; },
        favorites() { return '<div class="favorites"><h2>المفضلة</h2></div>'; },
        login() { return AuthScreens.login(MostamalApp.config); },
        register() { return AuthScreens.register(MostamalApp.config); }
    }
};

class MobileRouter {
    constructor() { this.routes = []; }
    register(path, handler) { this.routes.push({ path, handler, regex: this.pathToRegex(path) }); }
    pathToRegex(path) { return new RegExp('^' + path.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'); }
    navigate(url) {
        for (const route of this.routes) {
            const match = url.match(route.regex);
            if (match) {
                const content = route.handler(match.groups || {});
                const el = document.getElementById('page-content');
                if (el) el.innerHTML = content;
                return;
            }
        }
    }
}

// Auto-init
document.addEventListener('DOMContentLoaded', () => MostamalApp.init());
"""
},

"product_components": {
    "order": 1, "lang": "javascript",
    "exports": "ProductCard,ProductGrid,ProductDetail",
    "content": r"""// Mostamal Hawaa — Product Components
function ProductCard(product) {
    const formatPrice = (p) => new Intl.NumberFormat('ar-SA').format(p) + ' ر.س';
    const timeAgo = (d) => {
        const diff = Date.now() - new Date(d).getTime();
        const days = Math.floor(diff / 86400000);
        if (days === 0) return 'اليوم';
        if (days === 1) return 'أمس';
        if (days < 7) return `منذ ${days} أيام`;
        return new Date(d).toLocaleDateString('ar-SA');
    };

    return `
    <div class="product-card" onclick="location.href='/product/${product.id}'">
        <div class="product-image">
            <img src="${product.images?.[0] || '/assets/no-image.png'}" alt="${product.title}" loading="lazy">
            ${product.featured ? '<span class="badge featured">مميز</span>' : ''}
            ${product.urgent ? '<span class="badge urgent">عاجل</span>' : ''}
            <button class="fav-btn ${product.favorited?'active':''}" onclick="event.stopPropagation();toggleFavorite('${product.id}')">
                <i class="icon-heart"></i>
            </button>
        </div>
        <div class="product-info">
            <h3 class="product-title">${product.title}</h3>
            <p class="product-price">${formatPrice(product.price)}</p>
            <div class="product-meta">
                <span><i class="icon-map-pin"></i> ${product.city || 'غير محدد'}</span>
                <span><i class="icon-clock"></i> ${timeAgo(product.created_at)}</span>
            </div>
        </div>
    </div>`;
}

function ProductGrid(products, title) {
    return `
    <div class="products-section">
        ${title ? `<h2 class="section-title">${title}</h2>` : ''}
        <div class="products-grid">
            ${products.map(p => ProductCard(p)).join('')}
        </div>
    </div>`;
}

function ProductDetail(product) {
    const formatPrice = (p) => new Intl.NumberFormat('ar-SA').format(p) + ' ر.س';
    return `
    <div class="product-detail-page">
        <div class="product-gallery">
            <div class="gallery-main"><img src="${product.images?.[0] || '/assets/no-image.png'}" id="mainImage"></div>
            <div class="gallery-thumbs">
                ${(product.images||[]).map((img,i) => `<img src="${img}" class="${i===0?'active':''}" onclick="document.getElementById('mainImage').src='${img}'">`).join('')}
            </div>
        </div>
        <div class="product-info-detail">
            <h1>${product.title}</h1>
            <p class="price">${formatPrice(product.price)}</p>
            <div class="seller-info">
                <img src="${product.seller?.avatar || '/assets/avatar.png'}" class="seller-avatar">
                <div><strong>${product.seller?.name}</strong><small>${product.seller?.rating}⭐ (${product.seller?.reviews} تقييم)</small></div>
            </div>
            <div class="product-description">${product.description || ''}</div>
            <div class="product-specs">
                ${Object.entries(product.specs||{}).map(([k,v]) => `<div class="spec-row"><span class="spec-label">${k}</span><span class="spec-value">${v}</span></div>`).join('')}
            </div>
            <div class="product-actions">
                <button class="btn-primary btn-block" onclick="startChat('${product.seller?.id}')"><i class="icon-message-circle"></i> تواصل مع البائع</button>
                <button class="btn-secondary" onclick="callSeller('${product.seller?.phone}')"><i class="icon-phone"></i> اتصل</button>
            </div>
        </div>
    </div>`;
}

async function toggleFavorite(productId) {
    const store = window.masStore;
    const existing = await store.get('favorites', productId);
    if (existing) { await store.delete('favorites', productId); }
    else { await store.save('favorites', { id: productId, added_at: new Date().toISOString() }); }
}
"""
},

"mostamal_css": {
    "order": 2, "lang": "css",
    "exports": "",
    "content": r"""/* Mostamal Hawaa — Custom Styles */
:root{--mostamal-primary:#E91E63;--mostamal-secondary:#FFC107;--mostamal-bg:#FAFAFA}
.mostamal-home{padding:0}
.search-hero{padding:20px;background:var(--mostamal-primary);text-align:center}
.search-hero .search-input{width:100%;max-width:500px;padding:12px 20px;border:none;border-radius:25px;font-size:16px;text-align:right}
.search-hero .search-btn{position:absolute;left:16px;top:50%;transform:translateY(-50%);background:transparent;border:none}
.categories-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:16px}
.cat-item{display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px;background:#fff;border-radius:12px;text-decoration:none;color:var(--dark);box-shadow:0 2px 4px rgba(0,0,0,.05);transition:.2s}
.cat-item:hover{transform:translateY(-2px);box-shadow:0 4px 8px rgba(0,0,0,.1)}
.cat-item i{font-size:24px;color:var(--mostamal-primary)}
.section-title{padding:16px;font-size:18px;font-weight:700}
.products-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:0 16px}
.product-card{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,.05);transition:.2s;cursor:pointer}
.product-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.1)}
.product-image{position:relative;aspect-ratio:4/3;overflow:hidden}
.product-image img{width:100%;height:100%;object-fit:cover}
.product-image .badge{position:absolute;top:8px;right:8px;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;color:#fff}
.badge.featured{background:var(--mostamal-primary)}.badge.urgent{background:var(--danger)}
.fav-btn{position:absolute;top:8px;left:8px;width:32px;height:32px;border:none;background:rgba(255,255,255,.9);border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer}
.fav-btn.active{color:var(--danger)}
.product-info{padding:12px}
.product-title{font-size:14px;font-weight:500;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.product-price{font-size:16px;font-weight:700;color:var(--mostamal-primary);margin-bottom:8px}
.product-meta{display:flex;justify-content:space-between;font-size:11px;color:var(--gray)}
.product-meta span{display:flex;align-items:center;gap:4px}
/* Product Detail */
.product-gallery .gallery-main{aspect-ratio:4/3;overflow:hidden;border-radius:12px}
.product-gallery .gallery-main img{width:100%;height:100%;object-fit:cover}
.gallery-thumbs{display:flex;gap:8px;margin-top:8px;overflow-x:auto}
.gallery-thumbs img{width:60px;height:60px;object-fit:cover;border-radius:8px;border:2px solid transparent;cursor:pointer}
.gallery-thumbs img.active{border-color:var(--mostamal-primary)}
.seller-info{display:flex;align-items:center;gap:12px;padding:16px;background:#f5f5f5;border-radius:12px;margin:16px 0}
.seller-avatar{width:48px;height:48px;border-radius:50%}
.product-specs{margin:16px 0}.spec-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee}
.product-actions{display:flex;gap:12px;margin-top:20px}
.btn-secondary{padding:12px 24px;border:2px solid var(--mostamal-primary);color:var(--mostamal-primary);background:#fff;border-radius:var(--radius);font-weight:600;cursor:pointer}
/* Plan badge */
.plan-badge{padding:2px 8px;border-radius:12px;font-size:11px;font-weight:bold}
.plan-badge.trial{background:#fff3e0;color:#e65100}.plan-badge.basic{background:#e3f2fd;color:#1565c0}
.plan-badge.premium{background:#f3e5f5;color:#7b1fa2}.plan-badge.enterprise{background:#e8f5e9;color:#2e7d32}
"""
}
}


async def main():
    print("=" * 60)
    print("QDML — MAS-SAAS Dashboard + Mostamal Hawaa App")
    print("=" * 60)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"})
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ MAS-SAAS Project ═══
    print("\n[1/4] MAS-SAAS Platform...")
    try: await engine.create_project("MAS-SAAS", "mas-saas", "Multi-tenant SaaS platform for app building")
    except: pass
    try: await engine.create_module("mas-saas", "Dashboard", "saas-dashboard", tier="frontend", app="saas")
    except: pass
    try: await engine.create_component("saas-dashboard", "SAAS Dashboard", "saas-dashboard-app", kind="screen", target="mas-js", project_slug="mas-saas")
    except: pass

    for name, data in SAAS_DASHBOARD_BULKS.items():
        await engine.create_bulk("saas-dashboard-app", name, data["content"], lang=data["lang"],
            bulk_order=data["order"], exports=data.get("exports",""), project_slug="mas-saas")
    print(f"  ✅ SAAS Dashboard: {len(SAAS_DASHBOARD_BULKS)} bulks")

    # ═══ Mostamal Hawaa ═══
    print("\n[2/4] Mostamal Hawaa App...")
    try: await engine.create_project("Mostamal Hawaa", "mostamal-hawaa", "E-commerce classified ads platform")
    except: pass
    try: await engine.create_module("mostamal-hawaa", "Mobile App", "mobile-app", tier="frontend", app="mostamal")
    except: pass
    try: await engine.create_component("mobile-app", "Mostamal Hawaa App", "mostamal-app", kind="screen", target="mas-js", project_slug="mostamal-hawaa")
    except: pass

    for name, data in MOSTAMAL_HAWAA_BULKS.items():
        await engine.create_bulk("mostamal-app", name, data["content"], lang=data["lang"],
            bulk_order=data["order"], exports=data.get("exports",""), project_slug="mostamal-hawaa")
    print(f"  ✅ Mostamal Hawaa: {len(MOSTAMAL_HAWAA_BULKS)} bulks")

    # ═══ Compile All ═══
    print("\n[3/4] Compiling...")
    gen = Path("/srv/apps/ai-first/mas-front/_generated")

    compilations = [
        ("saas-dashboard-app", "mas-saas", gen / "saas" / "saas-dashboard.js"),
        ("mostamal-app", "mostamal-hawaa", gen / "mostamal" / "mostamal-app.js"),
    ]

    for comp, proj, out in compilations:
        code = await engine.compile_component(comp, project_slug=proj)
        if code:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(code, encoding="utf-8")
            print(f"  📦 {out.name}: {code.count(chr(10))+1} lines")

    # ═══ Final Stats ═══
    print("\n[4/4] Final statistics...")
    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"COMPLETE PLATFORM:")
    print(f"  Projects:   {stats['projects']}")
    print(f"  Modules:    {stats['modules']}")
    print(f"  Components: {stats['components']}")
    print(f"  Bulks:      {stats['bulks']}")
    print(f"  Lines:      {stats['total_lines']:,}")
    print(f"  DB Size:    {stats['db_size_mb']} MB")
    print(f"{'=' * 60}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
