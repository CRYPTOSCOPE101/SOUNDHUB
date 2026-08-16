#!/usr/bin/env python3
"""Capture fresh README screenshots of the current (bandcamp-style) UI.

Replaces the stale pre-redesign PNGs in screenshots/:
  main-light.png          — landing page (full width, first viewport)
  projects.png            — /projects (repo list)
  repo-page.png           — /projects/<id> (repo page with file tree)
  repo-page-branches.png  — /projects/<id>/branches

Usage (from backend/):
  .venv/bin/python scripts/screenshots.py [--base http://localhost:5173] [--out ../screenshots]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5173")
    ap.add_argument("--out", default=pathlib.Path(__file__).resolve().parents[2] / "screenshots")
    ap.add_argument("--username", default="demo")
    ap.add_argument("--password", default="demo123")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": args.height})

        def shot(name: str) -> None:
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(800)
            print(f"  shot {name}: {page.url}")
            page.screenshot(path=str(out / name))

        # ---- landing (no auth needed) ----
        page.goto(f"{args.base}/", wait_until="networkidle")
        shot("main-light.png")

        # ---- sign in as demo ----
        page.goto(f"{args.base}/login", wait_until="networkidle")
        page.fill('input[type="text"][placeholder="username"]', args.username)
        page.fill('input[type="password"]', args.password)
        page.click('form button:text-is("Sign in")')  # NOT "Sign in with wallet"
        page.wait_for_url(f"{args.base}/projects*", timeout=15000)
        shot("projects.png")

        # ---- first project: repo page ----
        repo_href = page.get_attribute(".project-card", "href")
        if not repo_href:
            raise SystemExit("no .project-card found — is demo logged in?")
        page.goto(f"{args.base}{repo_href}", wait_until="networkidle")
        shot("repo-page.png")

        # ---- branches of that project ----
        branches_href = page.get_attribute("a.repo-tab", "href")
        if not branches_href:
            raise SystemExit("no .repo-tab found — repo page didn't render")
        page.goto(f"{args.base}{branches_href}", wait_until="networkidle")
        shot("repo-page-branches.png")

        browser.close()
    print(f"✓ screenshots written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
