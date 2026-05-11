// Dashboard Kit — Layout (Sidebar + Header + Content)
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

// Dashboard Kit — Widgets (StatsCard, DataTable, Chart)
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
