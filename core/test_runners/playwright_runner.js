#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function loadPlaywright() {
  try {
    return require("playwright-core");
  } catch (error) {
    return null;
  }
}

function serializeError(error) {
  return {
    name: error && error.name ? error.name : "Error",
    message: error && error.message ? error.message : String(error),
    stack: error && error.stack ? String(error.stack).split("\n").slice(0, 12).join("\n") : "",
  };
}

async function main() {
  const payloadPath = process.argv[2];
  if (!payloadPath) throw new Error("payload path is required");
  const payload = JSON.parse(fs.readFileSync(payloadPath, "utf8"));
  const playwright = loadPlaywright();
  if (!playwright) {
    throw new Error("playwright-core is not installed. Run npm install playwright-core in /srv/apps/ai-first/core.");
  }

  const events = [];
  const failedRequests = [];
  const badResponses = [];
  const consoleErrors = [];
  const consoleWarnings = [];
  const startedAt = Date.now();
  const log = (...items) => events.push({ type: "log", text: items.map((item) => String(item)).join(" ") });
  const chromiumPath = payload.executablePath
    || process.env.PLAYWRIGHT_CHROMIUM_PATH
    || (fs.existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : "")
    || (fs.existsSync("/usr/bin/chromium-browser") ? "/usr/bin/chromium-browser" : "")
    || (fs.existsSync("/snap/bin/chromium") ? "/snap/bin/chromium" : "");
  let browser;
  let page;
  try {
    browser = await playwright.chromium.launch({
      executablePath: chromiumPath,
      headless: payload.headless !== false,
      args: ["--no-sandbox", "--disable-gpu"],
    });
    const context = await browser.newContext({
      viewport: payload.viewport || { width: 1366, height: 768 },
      ignoreHTTPSErrors: true,
      locale: payload.locale || "ar-EG",
    });
    page = await context.newPage();
    page.on("console", (msg) => {
      const item = { type: "console", level: msg.type(), text: msg.text(), location: msg.location() };
      events.push(item);
      if (msg.type() === "error") consoleErrors.push(item);
      if (msg.type() === "warning") consoleWarnings.push(item);
    });
    page.on("pageerror", (error) => events.push({ type: "pageerror", ...serializeError(error) }));
    page.on("requestfailed", (request) => {
      const item = {
        type: "requestfailed",
        url: request.url(),
        failure: request.failure() ? request.failure().errorText : "",
      };
      failedRequests.push(item);
      events.push(item);
    });
    page.on("response", (response) => {
      if (response.status() >= 400) {
        const item = { type: "badresponse", status: response.status(), url: response.url() };
        badResponses.push(item);
        events.push(item);
      }
    });

    const api = {
      browser,
      context,
      page,
      log,
      project: payload.project || {},
      auth: payload.auth || {},
      test: payload.test || {},
      env: payload.env || {},
      goto: async (url, options = {}) => page.goto(url, {
        waitUntil: options.waitUntil || "domcontentloaded",
        timeout: options.timeout || payload.timeout_ms || 30000,
      }),
      wait: (ms) => page.waitForTimeout(ms),
      expectVisible: async (selector, timeout = 5000) => {
        await page.locator(selector).first().waitFor({ state: "visible", timeout });
      },
      click: async (selector, options = {}) => page.locator(selector).first().click(options),
      fill: async (selector, value, options = {}) => page.locator(selector).first().fill(value, options),
      text: async (selector) => page.locator(selector).first().innerText(),
    };

    if (payload.auth_script) {
      const runAuth = new Function("api", `"use strict"; return (async () => {\n${payload.auth_script}\n})();`);
      await runAuth(api);
    }
    if (payload.script) {
      const runTest = new Function("api", `"use strict"; return (async () => {\n${payload.script}\n})();`);
      await runTest(api);
    }

    const title = page ? await page.title().catch(() => "") : "";
    const finalUrl = page ? page.url() : "";
    if (payload.screenshot_path && page) {
      fs.mkdirSync(path.dirname(payload.screenshot_path), { recursive: true });
      await page.screenshot({ path: payload.screenshot_path, fullPage: true }).catch((error) => {
        events.push({ type: "screenshot-error", ...serializeError(error) });
      });
    }
    if (payload.fail_on_bad_response && badResponses.length) {
      throw new Error(`bad browser responses: ${badResponses.map((item) => `${item.status} ${item.url}`).join(", ")}`);
    }
    if (payload.fail_on_console_error && consoleErrors.length) {
      throw new Error(`console errors: ${consoleErrors.map((item) => item.text).join(" | ")}`);
    }
    await browser.close();
    process.stdout.write(JSON.stringify({
      ok: true,
      title,
      url: finalUrl,
      events,
      failed_requests: failedRequests,
      bad_responses: badResponses,
      console_errors: consoleErrors,
      console_warnings: consoleWarnings,
      duration_ms: Date.now() - startedAt,
      screenshot_path: payload.screenshot_path || "",
    }));
  } catch (error) {
    if (payload.screenshot_path && page) {
      try {
        fs.mkdirSync(path.dirname(payload.screenshot_path), { recursive: true });
        await page.screenshot({ path: payload.screenshot_path, fullPage: true });
      } catch (_error) {}
    }
    if (browser) {
      await browser.close().catch(() => {});
    }
    process.stdout.write(JSON.stringify({
      ok: false,
      error: serializeError(error),
      events,
      duration_ms: Date.now() - startedAt,
      screenshot_path: payload.screenshot_path || "",
    }));
    process.exitCode = 1;
  }
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({ ok: false, error: serializeError(error), events: [] }));
  process.exitCode = 1;
});
