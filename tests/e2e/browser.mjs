// End-to-end run of a freshly generated Aso app (aso new) in a real browser.
import { chromium } from "playwright";
import { execSync } from "node:child_process";

const BASE = process.env.APP_URL ?? "http://127.0.0.1:8766";
const DB = process.env.APP_DB;  // path to the app's database/database.sqlite
const results = [];
const check = (name, ok, extra = "") => { results.push([name, ok]); console.log(`${ok ? "PASS" : "FAIL"} ${name} ${extra}`); };
const step = async (name, fn) => { try { await fn(); } catch (e) { check(name, false, String(e).split("\n")[0]); } };

const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
const page = await browser.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push(String(e)));
const email = `ada${Date.now()}@example.com`;

await step("welcome page renders", async () => {
  await page.goto(BASE + "/");
  await page.waitForSelector("#app *", { timeout: 8000 });
  check("welcome page renders", (await page.content()).includes('data-page="app"'));
});

await step("register", async () => {
  await page.goto(BASE + "/register");
  await page.fill('input[name="name"]', "Ada Lovelace");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', "password-123-Secure");
  await page.fill('input[name="password_confirmation"]', "password-123-Secure");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.startsWith("/register"), { timeout: 8000 });
  check("register redirects away from /register", true, page.url());
});

await step("unverified user sees verify-email", async () => {
  await page.goto(BASE + "/dashboard");
  await page.waitForLoadState("networkidle");
  check("unverified user sees verify-email", page.url().includes("/email/verify") || page.url().includes("verify"), page.url());
});

await step("verified user reaches dashboard", async () => {
  execSync(`sqlite3 ${DB} "update users set email_verified_at = datetime('now') where email = '${email}'"`);
  await page.goto(BASE + "/dashboard");
  await page.waitForLoadState("networkidle");
  check("verified user reaches dashboard", new URL(page.url()).pathname === "/dashboard", page.url());
  check("dashboard shows user name", (await page.content()).includes("Ada Lovelace"));
});

await step("profile update with flash", async () => {
  await page.goto(BASE + "/settings/profile");
  await page.fill('input[name="name"]', "Ada King");
  await page.getByRole("button", { name: "Save" }).click();
  await page.waitForTimeout(1500);
  const name = execSync(`sqlite3 ${DB} "select name from users where email = '${email}'"`).toString().trim();
  check("profile name saved", name === "Ada King", name);
});

await step("profile validation error", async () => {
  await page.goto(BASE + "/settings/profile");
  await page.fill('input[name="name"]', "");
  await page.fill('input[name="email"]', "not-an-email");
  await page.evaluate(() => document.querySelectorAll("form").forEach((f) => (f.noValidate = true)));  // test server-side rules
  await page.getByRole("button", { name: "Save" }).click();
  await page.waitForTimeout(1500);
  const html = await page.content();
  check("validation messages shown", html.includes("field is required") || html.includes("valid email"), "");
});

await step("logout", async () => {
  const token = (await page.context().cookies()).find((c) => c.name === "XSRF-TOKEN")?.value;
  await page.evaluate(async (t) => { await fetch("/logout", { method: "POST", headers: { "X-XSRF-TOKEN": decodeURIComponent(t), "X-Inertia": "true" } }); }, token);
  await page.goto(BASE + "/dashboard");
  await page.waitForLoadState("networkidle");
  check("logged out user redirected to login", page.url().includes("/login"), page.url());
});

await step("wrong password", async () => {
  await page.goto(BASE + "/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', "wrong-password");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);
  check("wrong password shows error", (await page.content()).includes("These credentials do not match our records."));
});

await step("login", async () => {
  await page.fill('input[name="password"]', "password-123-Secure");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => u.pathname === "/dashboard", { timeout: 8000 });
  check("login lands on dashboard", true);
});

await browser.close();
if (errors.length) console.log("browser errors:\n  " + errors.slice(0, 8).join("\n  "));
const failed = results.filter(([, ok]) => !ok).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
