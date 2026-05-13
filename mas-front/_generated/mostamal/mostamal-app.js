// Mostamal Hawaa — Complete Mobile App Shell
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

// Mostamal Hawaa — Product Components
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

/* Mostamal Hawaa — Custom Styles */
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
