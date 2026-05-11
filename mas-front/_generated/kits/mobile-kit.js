// Mobile Kit — Shell (Header + Footer + SideMenu)
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

// Mobile Kit — Auth Screens (Login, Register, Reset, Splash)
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

/* Mobile Kit CSS */
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
