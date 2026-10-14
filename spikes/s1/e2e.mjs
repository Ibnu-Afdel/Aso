// S-1 end-to-end run against the real @inertiajs/react 3.8 client.
import { chromium } from "playwright";
import { writeFileSync, rmSync } from "node:fs";

const BASE = "http://127.0.0.1:8765";
const results = [];
const check = (name, ok, extra = "") => { results.push([name, ok]); console.log(`${ok ? "PASS" : "FAIL"} ${name} ${extra}`); };

rmSync("version.txt", { force: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME ?? "/usr/bin/chromium" });
const page = await browser.newPage();
const requests = [];
page.on("request", (r) => { if (r.url().startsWith(BASE) && !r.url().includes("/build/")) requests.push(`${r.method()} ${r.url().replace(BASE, "")} xsrf=${r.headers()["x-xsrf-token"] ? "yes" : "no"} inertia=${r.headers()["x-inertia"] ?? "-"}`); });
page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text()); });

// 1. first visit: HTML with the script-element page object
const first = await page.goto(`${BASE}/posts/create`);
const html = await first.text();
check("first visit renders <script data-page=app type=application/json>", html.includes('<script data-page="app" type="application/json">'));
check("slashes escaped in page JSON", html.includes('\\/posts\\/create') && !html.includes('"/posts/create"'));
await page.getByTestId("submit").waitFor();

// 2. invalid submit -> redirect back -> props.errors
await page.getByTestId("title").fill("ab");
await page.getByTestId("submit").click();
await page.getByTestId("error-title").waitFor({ timeout: 5000 });
check("invalid form shows Laravel message", (await page.getByTestId("error-title").textContent()) === "The title field must be at least 3 characters.");
check("URL stays on the form", page.url() === `${BASE}/posts/create`);
check("POST carried X-XSRF-TOKEN from cookie", requests.some((r) => r.startsWith("POST /posts xsrf=yes")));

// 3. fix -> redirect to index with page.flash + deferred prop reading the DB
await page.getByTestId("title").fill("Hello world");
await page.getByTestId("submit").click();
await page.getByTestId("flash").waitFor({ timeout: 5000 });
check("flash arrives in page.flash", (await page.getByTestId("flash").textContent()) === "Post created.");
check("redirected to /posts", page.url() === `${BASE}/posts`);
await page.locator('[data-testid="posts"] li').first().waitFor({ timeout: 5000 });
check("deferred prop loaded via await Post.all()", (await page.locator('[data-testid="posts"] li').allTextContents()).join() === "Hello world");
check("deferred follow-up request was a partial reload", requests.some((r) => r.startsWith("GET /posts xsrf") && r.includes("inertia=true")));

// 4. useHttp against a web route returning a dict
await page.getByTestId("stats").click();
await page.waitForFunction(() => document.getElementById("count")?.textContent === "count: 1", null, { timeout: 5000 });
check("useHttp got the dict JSON", true);

// 5. flash shown once: navigate away and back
await page.getByTestId("to-create").click();
await page.getByTestId("submit").waitFor();
await page.getByTestId("to-index").click();
await page.getByTestId("posts").waitFor({ timeout: 5000 });
check("flash not shown again", (await page.getByTestId("flash").count()) === 0);

// 6. version mismatch after a redirect: 409 -> full reload, flash survives
await page.getByTestId("to-create").click();
await page.getByTestId("title").waitFor();
writeFileSync("version.txt", "v2-redeployed");
let saw409 = false;
page.on("response", (r) => { if (r.status() === 409) saw409 = true; });
await page.getByTestId("title").fill("Second post");
await page.getByTestId("submit").click();
await page.getByTestId("flash").waitFor({ timeout: 8000 });
check("409 version mismatch happened", saw409);
check("flash survived the 409 full reload", (await page.getByTestId("flash").textContent()) === "Post created.");
const pageJson = await page.evaluate(() => JSON.parse(document.querySelector('script[data-page="app"]').textContent));
check("page reloaded with new version", pageJson.version === "v2-redeployed");

rmSync("version.txt", { force: true });
await browser.close();
console.log("\nrequests:\n" + requests.join("\n"));
const failed = results.filter(([, ok]) => !ok).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
