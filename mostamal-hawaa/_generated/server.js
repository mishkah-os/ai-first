// Mostamal Hawaa runtime bridge.
// This service deliberately serves the original app source and swaps only the
// MAS runtime to AI-First MAS v2 plus a small legacy adapter.
import { createServer } from "http";
import { createReadStream, existsSync, readFileSync, statSync } from "fs";
import { extname, join, normalize, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const PORT = parseInt(process.env.PORT || "9001", 10);
const PUBLIC_ROOT = resolve(process.env.PUBLIC_ROOT || "/srv/apps/os/static/app/mostamal_hawaa");
const AI_FIRST_CORE = resolve(process.env.AI_FIRST_CORE || "/srv/apps/ai-first/core");
const OS_LIB2 = resolve(process.env.OS_LIB2 || "/srv/apps/os/static/lib2");
const APP_SLUG = process.env.APP_SLUG || "mostamal-hawaa";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml; charset=utf-8",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".woff": "font/woff",
  ".woff2": "font/woff2"
};

function json(res, status, payload) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"
  });
  res.end(JSON.stringify(payload));
}

function within(root, filePath) {
  const normalized = normalize(filePath);
  return normalized === root || normalized.startsWith(root + "/");
}

function fileFrom(root, pathname) {
  const clean = decodeURIComponent(pathname).replace(/^\/+/, "");
  const candidate = resolve(root, clean);
  return within(root, candidate) ? candidate : null;
}

function sendFile(res, filePath) {
  if (!filePath || !existsSync(filePath) || !statSync(filePath).isFile()) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("Not Found");
    return;
  }
  const ext = extname(filePath);
  res.writeHead(200, {
    "Content-Type": MIME[ext] || "application/octet-stream",
    "Cache-Control": ext === ".html" ? "no-store" : "public, max-age=60"
  });
  createReadStream(filePath).pipe(res);
}

function injectRuntime(html) {
  let next = html;
  const runtimeScripts = '<script src="/__aifirst/mas.core.v2.js"></script>\n  <script src="/__aifirst/mas-v2-legacy-compat.js"></script>';
  next = next.replace(
    /<script\s+src=["']https:\/\/os\.ai-auto\.cloud\/lib2\/mas\.core\.js["']><\/script>/i,
    runtimeScripts
  );
  next = next.replace(
    /<script\s+src=["']https:\/\/os\.ai-auto\.cloud\/lib2\/mas-utils\.js["']><\/script>/i,
    '<script src="/__os-lib2/mas-utils.js"></script>'
  );
  next = next.replace(
    /<script\s+src=["']https:\/\/os\.ai-auto\.cloud\/lib2\/mas-rest\.js["']><\/script>/i,
    '<script src="/__os-lib2/mas-rest.js"></script>'
  );
  if (!next.includes("/__aifirst/mas.core.v2.js")) {
    next = next.replace(
      /<script\s+type=["']module["']\s+src=["']\.\/src\/app\.js["']><\/script>/i,
      runtimeScripts + '\n  <script type="module" src="./src/app.js"></script>'
    );
  }
  next = next.replace(
    "</head>",
    '  <meta name="ai-first-runtime" content="mas-v2-original-source" />\n</head>'
  );
  return next;
}

function sendIndex(res) {
  const indexPath = join(PUBLIC_ROOT, "index.html");
  if (!existsSync(indexPath)) {
    json(res, 500, { ok: false, error: "index.html missing", publicRoot: PUBLIC_ROOT });
    return;
  }
  const html = injectRuntime(readFileSync(indexPath, "utf8"));
  res.writeHead(200, { "Content-Type": MIME[".html"], "Cache-Control": "no-store" });
  res.end(html);
}

const server = createServer((req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);

  if (req.method === "OPTIONS") {
    json(res, 204, {});
    return;
  }

  if (url.pathname === "/health") {
    json(res, 200, {
      ok: true,
      status: "ok",
      app: APP_SLUG,
      port: PORT,
      runtime: "original-source-mas-v2-compat",
      sourceRoot: PUBLIC_ROOT,
      masCore: join(AI_FIRST_CORE, "mas.core.v2.js"),
      masCompat: join(AI_FIRST_CORE, "mas-v2-legacy-compat.js"),
      masStore: "v3"
    });
    return;
  }

  if (url.pathname === "/api/config") {
    json(res, 200, {
      ok: true,
      app_name: "Mostamal Hawaa",
      app_slug: APP_SLUG,
      runtime: "mas-v2-original-source",
      source_root: PUBLIC_ROOT,
      api_host: "https://os.ai-auto.cloud",
      ws_url: "wss://os.ai-auto.cloud/ws/v3"
    });
    return;
  }

  if (url.pathname === "/" || url.pathname === "/index.html") {
    sendIndex(res);
    return;
  }

  if (url.pathname.startsWith("/__aifirst/")) {
    sendFile(res, fileFrom(AI_FIRST_CORE, url.pathname.replace("/__aifirst/", "")));
    return;
  }

  if (url.pathname.startsWith("/__os-lib2/")) {
    sendFile(res, fileFrom(OS_LIB2, url.pathname.replace("/__os-lib2/", "")));
    return;
  }

  const staticPath = fileFrom(PUBLIC_ROOT, url.pathname);
  if (staticPath && existsSync(staticPath) && statSync(staticPath).isFile()) {
    sendFile(res, staticPath);
    return;
  }

  sendIndex(res);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`[Mostamal Hawaa] ${APP_SLUG} serving ${PUBLIC_ROOT} on http://0.0.0.0:${PORT}`);
});
