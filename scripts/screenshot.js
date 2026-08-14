// Headless screenshots of the SoundHub main page (light + dark themes).
// Usage: node scripts/screenshot.js
// Requires: puppeteer in frontend/node_modules, PUPPETEER_CACHE_DIR set.
const puppeteer = require("../frontend/node_modules/puppeteer");
const fs = require("fs");
const path = require("path");

const BASE = "http://localhost:5173";
const OUT_DIR = path.join(__dirname, "..", "screenshots");

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
  const inputs = await page.$$("input");
  if (inputs.length < 2) throw new Error("login form not found");
  await inputs[0].type("demo");
  await inputs[1].type("demo123");
  await page.evaluate(() => document.querySelector("form").requestSubmit());
  await page.waitForFunction(() => location.pathname === "/projects", { timeout: 15000 });
  // wait until the projects grid actually renders content
  await page
    .waitForFunction(
      () => {
        const t = document.body.innerText;
        return t.includes("Neon Dreams") && !t.includes("Loading");
      },
      { timeout: 15000 }
    )
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 800));
}

async function shot(page, file) {
  // full-page capture at 2x device scale for crisp README images
  await page.screenshot({ path: path.join(OUT_DIR, file), fullPage: true });
  console.log("saved screenshots/" + file);
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  await login(page);

  // light theme
  await page.evaluate(() => {
    localStorage.setItem("soundhub_theme", "light");
    document.documentElement.setAttribute("data-theme", "light");
  });
  await new Promise((r) => setTimeout(r, 400));
  await shot(page, "main-light.png");

  // dark theme
  await page.evaluate(() => {
    localStorage.setItem("soundhub_theme", "dark");
    document.documentElement.setAttribute("data-theme", "dark");
  });
  await new Promise((r) => setTimeout(r, 400));
  await shot(page, "main-dark.png");

  // repo page (light) — open Neon Dreams
  await page.evaluate(() => {
    localStorage.setItem("soundhub_theme", "light");
    document.documentElement.setAttribute("data-theme", "light");
  });
  const link = await page.$("a.project-card");
  if (link) {
    await Promise.all([
      page.waitForFunction(() => document.querySelector(".repo-tabs, .branch-selector"), { timeout: 15000 }),
      link.click(),
    ]);
    await new Promise((r) => setTimeout(r, 1000));
    await shot(page, "repo-page.png");

    // open the branch dropdown so branches are visible
    const sel = await page.$(".branch-selector");
    if (sel) {
      await sel.click();
      await new Promise((r) => setTimeout(r, 500));
      await shot(page, "repo-page-branches.png");
    }
  }

  await browser.close();
}

main().catch((err) => {
  console.error("Screenshot failed:", err.message);
  process.exit(1);
});
