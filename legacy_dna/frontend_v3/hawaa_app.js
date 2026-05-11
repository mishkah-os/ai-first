import DB from "./core/db.js";
import { app as masApp } from "./core/mas.js";
import { AppBody } from "./features/shell/ui.js";
import { orders as shellOrders, applyDocumentEnv } from "./features/shell/orders.js";
import { orders as composerOrders } from "./features/composer/orders.js";
import { deriveTables } from "./shared/logic/schema.js";
import { readStoredSession } from "./shared/logic/auth.js";

function compactVNode(node) {
  if (!node || typeof node !== "object") return node;
  if (Array.isArray(node.children)) {
    node.children = node.children.filter((child) => child !== null && child !== undefined && child !== false).map(compactVNode);
  }
  return node;
}

function tFactory(state) {
  return function t(key) {
    const lang = state.env.lang || "ar";
    // Local translation overrides
    const overrides = {
      "nav.classifieds": {
        ar: "إعلانات",
        en: "Classifieds"
      },
      "label.no_posts": {
        ar: "لا توجد منشورات",
        en: "No posts yet"
      },
      "label.following": {
        ar: "متابَع",
        en: "Following"
      },
      "field.governorate": {
        ar: "المحافظة",
        en: "Governorate"
      },
      "field.city": {
        ar: "المنطقة",
        en: "City"
      }
    };
    if (overrides[key] && overrides[key][lang]) {
      return overrides[key][lang];
    }
    return state.i18n?.dict?.[key]?.[lang] || state.i18n?.dict?.[key]?.ar || key;
  };
}

function snapshotData() {
  const tables = DB.snapshot?.tables || {};
  const data = {};
  Object.keys(tables).forEach((tableName) => {
    data[tableName] = DB.normalizeRows(tableName, tables[tableName]);
  });
  return data;
}

function initialState() {
  const storagePrefix = DB.runtime.storagePrefix || DB.runtime.appId || "sbn";
  const theme = localStorage.getItem(`${storagePrefix}:theme`) || "light";
  const lang = localStorage.getItem(`${storagePrefix}:lang`) || DB.runtime.lang || "ar";
  const storedSession = readStoredSession();
  let cartItems = [];
  try { cartItems = JSON.parse(localStorage.getItem(`${storagePrefix}:cart`) || "[]"); } catch (_error) { cartItems = []; }
  return {
    env: {
      lang,
      dir: lang === "ar" ? "rtl" : "ltr",
      theme,
      loading: true,
      connection: "idle",
      appId: DB.runtime.appId,
      storagePrefix,
      appName: DB.runtime.appName,
      appEmoji: DB.runtime.appEmoji,
      featureMode: DB.runtime.featureMode,
      enabledRoutes: DB.runtime.enabledRoutes || [],
      composerTypes: DB.runtime.composerTypes || [],
    },
    i18n: { dict: {} },
    schema: { schema: { tables: [] } },
    tables: {},
    data: {},
    ui: { route: DB.runtime.defaultRoute || "home", search: "", menuOpen: false, detail: null, previousRoute: DB.runtime.defaultRoute || "home", profileTab: "reels" },
    session: storedSession,
    auth: { open: false, loading: false, mode: "login", step: "form", phone: "", password: "", full_name: "", email: "", new_password: "", otp: "", flowToken: "", message: "", error: "" },
    subscription: { open: false, loading: false, message: "", error: "" },
    catalog: {},
    catalogLoading: false,
    catalogRefreshing: false,
    inbox: { conversationId: "", draft: "" },
    cart: { items: Array.isArray(cartItems) ? cartItems : [] },
    profileEdit: { open: false },
    composer: { open: false, step: "type", type: "reel", saving: false, uploading: false, mediaUrl: "", mediaType: "", error: "" },
    toast: "",
  };
}

function routeFromHash(data, tables) {
  const raw = String(location.hash || "").replace(/^#/, "");
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] !== "s" || !parts[1] || !parts[2]) return null;
  const type = decodeURIComponent(parts[1]);
  const slug = decodeURIComponent(parts[2]);
  const tableByType = {
    post: tables.posts,
    reel: tables.posts,
    product: tables.products,
    service: tables.services,
    classified: tables.classifieds,
    ad: tables.classifieds,
    knowledge: tables.articles,
    profile: tables.users,
  };
  const table = tableByType[type];
  const row = (data[table] || []).find((item) => String(item.share_slug || item.id || "") === slug || String(item.id || "") === slug);
  return row ? { route: type === "profile" ? "profile" : "detail", detail: { type, id: row.id } } : null;
}

const CATALOG_ROUTES = new Set(["marketplace", "services", "knowledge", "classifieds"]);
let mobileLoadingInstalled = false;
let lastCatalogRefreshAt = 0;
let catalogScrollBusy = false;

function catalogTableForRoute(state) {
  if (state.ui.route === "marketplace") return state.tables.products;
  if (state.ui.route === "services") return state.tables.services;
  if (state.ui.route === "knowledge") return state.tables.articles;
  if (state.ui.route === "classifieds") return state.tables.classifieds;
  return "";
}

function mergeRowsById(currentRows, nextRows) {
  const map = new Map();
  (Array.isArray(currentRows) ? currentRows : []).forEach((row) => {
    const id = row && row.id;
    if (id) map.set(String(id), row);
  });
  (Array.isArray(nextRows) ? nextRows : []).forEach((row) => {
    const id = row && row.id;
    if (!id) return;
    map.set(String(id), { ...(map.get(String(id)) || {}), ...row });
  });
  return Array.from(map.values());
}

function hasVisibleCatalogMore() {
  if (typeof document === "undefined") return true;
  const feed = document.querySelector("[data-catalog-feed]");
  if (!feed) return true;
  return feed.getAttribute("data-has-more") === "1";
}

function updateCatalogVisible(delta = 10) {
  if (!appRef) return;
  const current = appRef.getState();
  const route = current.ui.route;
  if (!CATALOG_ROUTES.has(route)) return;
  if (catalogScrollBusy) return;
  if (!hasVisibleCatalogMore()) return;
  catalogScrollBusy = true;
  appRef.setState((state) => {
    const catalog = state.catalog || {};
    const routeState = { visible: 10, category: "all", filter: "newest", query: "", ...(catalog[route] || {}) };
    return {
      ...state,
      catalogLoading: true,
      catalog: {
        ...catalog,
        [route]: { ...routeState, visible: Math.max(10, Number(routeState.visible) || 10) + delta },
      },
    };
  });
  window.setTimeout(() => {
    catalogScrollBusy = false;
    if (appRef) appRef.setState((state) => ({ ...state, catalogLoading: false }));
  }, 420);
}

async function refreshCatalogTopPage() {
  if (!appRef) return;
  const state = appRef.getState();
  const table = catalogTableForRoute(state);
  if (!table) return;
  const now = Date.now();
  if (now - lastCatalogRefreshAt < 25000) return;
  lastCatalogRefreshAt = now;
  appRef.setState((current) => ({ ...current, catalogRefreshing: true }));
  try {
    const [rows, stories] = await Promise.all([
      DB.load(table, { limit: 10, page: 1, fresh: true }).catch(() => []),
      state.tables.posts ? DB.load(state.tables.posts, { limit: 10, page: 1, fresh: true }).catch(() => []) : Promise.resolve([]),
    ]);
    appRef.setState((current) => ({
      ...current,
      data: {
        ...current.data,
        [table]: rows.length ? mergeRowsById(current.data[table] || [], rows) : (current.data[table] || []),
        ...(state.tables.posts && stories.length ? { [state.tables.posts]: mergeRowsById(current.data[state.tables.posts] || [], stories) } : {}),
      },
    }));
  } finally {
    if (appRef) appRef.setState((current) => ({ ...current, catalogRefreshing: false }));
  }
}

function installMobileLoadingControls() {
  if (mobileLoadingInstalled || typeof document === "undefined") return;
  const scroller = document.querySelector(".app-scroll");
  const shell = document.querySelector(".phone-shell");
  if (!scroller || !shell) {
    window.setTimeout(installMobileLoadingControls, 120);
    return;
  }
  mobileLoadingInstalled = true;

  const indicator = document.createElement("div");
  indicator.className = "pull-refresh-indicator";
  indicator.innerHTML = '<span class="pull-refresh-bubble"><i class="fa-solid fa-arrow-down"></i></span>';
  shell.appendChild(indicator);

  let startY = 0;
  let pullDistance = 0;
  let pulling = false;

  const setPull = (distance, refreshing = false) => {
    pullDistance = Math.max(0, Math.min(distance, 130));
    indicator.style.setProperty("--pull-distance", `${pullDistance}px`);
    indicator.classList.toggle("active", pullDistance > 0 || refreshing);
    indicator.classList.toggle("ready", pullDistance >= 78);
    indicator.classList.toggle("refreshing", refreshing);
    scroller.style.setProperty("--catalog-pull-distance", refreshing ? "94px" : `${pullDistance}px`);
    scroller.classList.toggle("is-pulling", pullDistance > 0 || refreshing);
    scroller.classList.toggle("is-refreshing", refreshing);
  };

  scroller.addEventListener("touchstart", (event) => {
    if (!appRef || scroller.scrollTop > 0) return;
    if (!CATALOG_ROUTES.has(appRef.getState().ui.route)) return;
    const touch = event.touches && event.touches[0];
    if (!touch) return;
    startY = touch.clientY;
    pulling = true;
  }, { passive: true });

  scroller.addEventListener("touchmove", (event) => {
    if (!pulling) return;
    const touch = event.touches && event.touches[0];
    if (!touch) return;
    const distance = touch.clientY - startY;
    if (distance <= 0 || scroller.scrollTop > 0) {
      pulling = false;
      setPull(0);
      return;
    }
    setPull(distance * 0.48);
  }, { passive: true });

  scroller.addEventListener("touchend", async () => {
    if (!pulling) return;
    pulling = false;
    if (pullDistance >= 78) {
      setPull(92, true);
      const startedAt = Date.now();
      await refreshCatalogTopPage();
      const elapsed = Date.now() - startedAt;
      if (elapsed < 850) await new Promise((resolve) => window.setTimeout(resolve, 850 - elapsed));
      window.setTimeout(() => setPull(0), 220);
      return;
    }
    setPull(0);
  }, { passive: true });

  scroller.addEventListener("scroll", () => {
    if (!appRef) return;
    if (!CATALOG_ROUTES.has(appRef.getState().ui.route)) return;
    if (!hasVisibleCatalogMore()) return;
    const remaining = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
    if (remaining < 240) updateCatalogVisible(10);
  }, { passive: true });
}

const orders = Object.assign({}, shellOrders, composerOrders);
let appRef = null;
const state = initialState();

applyDocumentEnv(state.env);

// Wait for MAS to be available
function initApp() {
  const MAS = window.MAS || window.Mishkah || window.M;
  if (!MAS || !MAS.app || !MAS.app.create) {
    console.warn('[SBN] MAS framework not ready yet, retrying...');
    setTimeout(initApp, 100);
    return;
  }
  
  console.log('[SBN] MAS framework loaded, initializing app...');
  
  // Set the body function before creating the app
  MAS.app.setBody((db) => compactVNode(AppBody(db, tFactory(db))));
  
  // Create app with state and orders
  appRef = MAS.app.create(state, orders);
  appRef.mount("#mas-app");
  installMobileLoadingControls();
  boot();
}

// Start initialization
initApp();

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("./service-worker.js").catch(() => {});
}

async function boot() {
  try {
    await DB.init(state.env.lang);
    const data = snapshotData();
    const tables = deriveTables(DB.schema);
    const hashRoute = routeFromHash(data, tables);
    const userId = appRef.getState().session.userId || "";
    const next = {
      ...appRef.getState(),
      env: { ...appRef.getState().env, loading: false, connection: DB.status().connection },
      i18n: { dict: DB.snapshot?.i18n || {} },
      schema: DB.schema,
      tables,
      data,
      session: { ...appRef.getState().session, userId, authenticated: Boolean(appRef.getState().session.token && userId) },
      ui: { ...appRef.getState().ui, ...(hashRoute || {}) },
    };
    appRef.setState(next);
    installMobileLoadingControls();
    installWatchers(next);
    DB.realtimeStore.on("status", (status) => {
      appRef.setState((current) => ({ ...current, env: { ...current.env, connection: status.connection } }));
    });
  } catch (error) {
    appRef.setState((current) => ({
      ...current,
      env: { ...current.env, loading: false, connection: "error" },
      toast: error?.message || "init-error",
    }));
    console.error("[SBN] boot failed", error);
  }
}

function installWatchers(current) {
  Object.values(current.tables).filter(Boolean).forEach((tableName) => {
    DB.watch(tableName, (rows) => {
      appRef.setState((state) => ({ ...state, data: { ...state.data, [tableName]: rows } }));
    }, { immediate: true, bootstrap: false });
  });
}

window.SBN_DB = DB;
window.MAS_APP_DB = DB;
window.SBN_APP = () => appRef;
window.MAS_APP = () => appRef;
