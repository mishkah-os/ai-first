"use strict";

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = __dirname;
const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 9010);
const UPSTREAM = (process.env.AI_AUTO_UPSTREAM || "https://ai-auto.cloud").replace(/\/+$/, "");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".ico": "image/x-icon"
};

function send(res, status, body, type = "application/json; charset=utf-8") {
  res.writeHead(status, {
    "Content-Type": type,
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-KEY",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
  });
  res.end(body);
}

function json(res, status, payload) {
  send(res, status, JSON.stringify(payload), "application/json; charset=utf-8");
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function safeStaticPath(urlPath) {
  const clean = urlPath === "/" ? "/index.html" : urlPath;
  const resolved = path.normalize(path.join(ROOT, clean.replace(/^\/+/, "")));
  if (!resolved.startsWith(ROOT)) return null;
  return resolved;
}

async function upstream(pathname, options = {}) {
  const response = await fetch(`${UPSTREAM}${pathname}`, options);
  const contentType = response.headers.get("content-type") || "application/json; charset=utf-8";
  const text = await response.text();
  return { status: response.status, contentType, text };
}

async function handleApi(req, res, url) {
  try {
    if (req.method === "GET" && url.pathname === "/health") {
      const health = await upstream("/health");
      json(res, 200, {
        status: "ok",
        service: "mas-erp-v2",
        upstream: UPSTREAM,
        upstream_status: health.status,
        upstream_body: JSON.parse(health.text || "{}")
      });
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/v7") {
      const raw = await readBody(req);
      const result = await upstream("/API/v7", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8", "Accept": "application/json" },
        body: raw || "{}"
      });
      send(res, result.status, result.text, result.contentType);
      return;
    }
    if (req.method === "GET" && url.pathname.startsWith("/api/document-")) {
      const result = await upstream(`${url.pathname}${url.search}`);
      send(res, result.status, result.text, result.contentType);
      return;
    }
    if (req.method === "POST" && ["/api/document-search", "/api/document-draft-save", "/api/document-finalize"].includes(url.pathname)) {
      const raw = await readBody(req);
      const result = await upstream(url.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8", "Accept": "application/json" },
        body: raw || "{}"
      });
      send(res, result.status, result.text, result.contentType);
      return;
    }
    json(res, 404, { Success: false, Error: "API route not found" });
  } catch (error) {
    json(res, 502, { Success: false, Error: error && error.message ? error.message : String(error), upstream: UPSTREAM });
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  if (req.method === "OPTIONS") {
    send(res, 204, "", "text/plain; charset=utf-8");
    return;
  }
  if (url.pathname === "/health" || url.pathname.startsWith("/api/")) {
    await handleApi(req, res, url);
    return;
  }
  if (url.pathname === "/favicon.ico") {
    send(res, 204, "", "text/plain; charset=utf-8");
    return;
  }
  const filePath = safeStaticPath(url.pathname);
  if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    send(res, 404, "Not Found", "text/plain; charset=utf-8");
    return;
  }
  const type = MIME[path.extname(filePath)] || "application/octet-stream";
  send(res, 200, fs.readFileSync(filePath), type);
});

server.listen(PORT, HOST, () => {
  console.log(`[mas-erp-v2] listening on http://${HOST}:${PORT}, upstream=${UPSTREAM}`);
});
