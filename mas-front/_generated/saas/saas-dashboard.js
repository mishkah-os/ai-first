// MAS-SAAS Developer Dashboard
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

// MAS-SAAS Pipeline Management Page
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

// MAS-SAAS Customer Management
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
