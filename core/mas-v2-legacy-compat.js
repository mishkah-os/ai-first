;(function(global){
  "use strict";

  var MAS = global.MAS;
  if (!MAS || !MAS.D || typeof MAS.app !== "function") {
    console.error("[MAS compat] MAS v2 must be loaded before mas-v2-legacy-compat.js");
    return;
  }

  var nativeApp = MAS.app;
  var nativeD = MAS.D;
  var bodyFactory = function(){ return nativeD.div({}, []); };
  var EVENT_KEY_RE = /^on([A-Z][A-Za-z0-9]*):(.*)$/;

  function normalizeChildren(children) {
    if (children == null) return [];
    return Array.isArray(children) ? children : [children];
  }

  function normalizeArgs(data, children) {
    if (data && typeof data === "object" && !data._t && data.attrs) {
      var attrs = {};
      for (var key in data.attrs) attrs[key] = data.attrs[key];
      if (data.key != null && attrs.key == null) attrs.key = data.key;
      if (children == null && data.children != null) children = data.children;
      return { attrs: attrs, children: normalizeChildren(children) };
    }
    return { attrs: data == null ? {} : data, children: normalizeChildren(children) };
  }

  function legacyTag(tag, data, children) {
    var args = normalizeArgs(data, children);
    var fn = nativeD[tag] || nativeD[String(tag).toLowerCase()];
    return fn(args.attrs, args.children);
  }

  var DSL = typeof Proxy !== "undefined" ? new Proxy({}, {
    get: function(_, prop) {
      if (prop === "h") return MAS.h;
      if (prop === "show" || prop === "unless") return nativeD[prop];
      if (typeof prop !== "string") return undefined;
      return function(data, children) {
        return legacyTag(prop, data, children);
      };
    }
  }) : {};

  function eventName(raw) {
    return String(raw || "click").replace(/^on/i, "").toLowerCase();
  }

  function normalizeOrders(orders) {
    var out = {};
    orders = orders || {};
    for (var key in orders) {
      var value = orders[key];
      var match = key.match(EVENT_KEY_RE);
      if (match) {
        out[match[2]] = { on: eventName(match[1]), do: value };
        continue;
      }
      if (typeof value === "function") {
        out[key] = value;
        continue;
      }
      if (value && typeof value === "object" && typeof value.do === "function") {
        var copy = {};
        for (var prop in value) copy[prop] = value[prop];
        copy.on = Array.isArray(copy.on) ? copy.on.map(eventName) : eventName(copy.on || "click");
        out[key] = copy;
      }
    }
    return out;
  }

  function mirrorGKeys(root) {
    if (!root || !root.querySelectorAll) return;
    var nodes = root.querySelectorAll("[gkey]");
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].setAttribute("data-m-gkey", nodes[i].getAttribute("gkey"));
    }
  }

  function legacyApp(bodyFn, database, orders) {
    return nativeApp(bodyFn, database, normalizeOrders(orders));
  }

  legacyApp.setBody = function(fn) {
    bodyFactory = typeof fn === "function" ? fn : bodyFactory;
    return legacyApp;
  };

  legacyApp.create = function(state, orders) {
    return nativeApp(function(db) {
      return bodyFactory(db, DSL);
    }, state || {}, normalizeOrders(orders));
  };

  legacyApp.normalizeOrders = normalizeOrders;
  legacyApp.native = nativeApp;

  MAS.DSL = DSL;
  MAS.legacyDSL = DSL;
  MAS.app = legacyApp;
  MAS.compat = {
    version: "legacy-mas-app-create-v1",
    normalizeOrders: normalizeOrders,
    mirrorGKeys: mirrorGKeys
  };

  if (typeof MAS.hook === "function") {
    MAS.hook("onRender", function(payload) {
      mirrorGKeys(payload && payload.root);
    });
  }

  global.MAS = MAS;
  global.Mishkah = MAS;
  global.M = MAS;
})(typeof globalThis !== "undefined" ? globalThis : window);
