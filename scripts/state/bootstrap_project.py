#!/usr/bin/env python3
"""
bootstrap_project.py — Plugin-agnostic project pack scaffolder.

Generates a minimal `projects/{slug}/project.config.json` conforming to
`schemas/project-config.schema.json`. Single-project per invocation. The
project slug is REQUIRED on the CLI (no hardcoded list).

Usage:
    python3 scripts/state/bootstrap_project.py --project <slug> [--domain URL] \\
        [--market TR] [--locale tr-TR] [--currency TRY] \\
        [--platform wordpress] [--profile local-service] [--profile ymyl] \\
        [--dfs-location-code 2792] [--dfs-language-code tr] \\
        [--out PATH] [--dry-run] [--force]

Env vars (read at runtime; no .env file is loaded):
    PSEO_WORKSPACE_ROOT   override default workspace_root path
    PSEO_PROJECTS_DIR     override default output dir (./projects)

Exit codes: 0 = success, non-zero on validation/error (stderr message).
Stdout contains the generated JSON when --dry-run is set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCHEMA_VERSION = "1.1"

DEFAULT_AI_BOTS = [
    "Googlebot", "Bingbot",
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "PerplexityBot", "ClaudeBot", "Claude-Web",
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def build_project_config(args: argparse.Namespace) -> dict:
    slug = args.project
    workspace_root = (
        os.getenv("PSEO_WORKSPACE_ROOT")
        or f"~/Documents/platinum-seo-engine/projects/{slug}"
    )
    cfg: dict = {
        "schema_version": SCHEMA_VERSION,
        "project_id": slug,
        "display_name": args.display_name or slug,
        "domain": args.domain,
        "market": args.market,
        "language": {
            "content_locale": args.locale,
            "content_variant": None,
        },
        "currency": args.currency,
        "platform": args.platform,
        "platform_seo_plugin": args.platform_seo_plugin,
        "profiles": args.profile or ["local-service"],
        "paths": {
            "workspace_root": workspace_root,
            "excel_filename": f"{slug}_MASTER.xlsx",
            "sf_exports_dir": "sf-exports",
            "staging_dir": "staging",
            "reports_dir": "reports",
            "blog_dir": "blog",
            "backups_dir": "_backups",
        },
        "gsc": {
            "site_url": args.gsc_site_url or args.domain,
            "default_date_range_days": 90,
        },
        "dataforseo": {
            "location_code": args.dfs_location_code,
            "language_code": args.dfs_language_code,
            "budget_credits_per_day": 500,
        },
        "brand": {
            "patterns": [slug],
            "mention_range": {"min": 4, "max": 7},
        },
        "ymyl_level": args.ymyl_level,
        "ai_bots": DEFAULT_AI_BOTS,
        "thresholds": {
            "quality_gate_pass_score": 70,
            "citability_pass_score": 70,
            "faq_count_exact": None,
            "brand_mention_min": 4,
            "brand_mention_max": 7,
        },
        "rules_overlay": "rules/project-rules.json",
        "platinum_seo_core_version": "^1.0",
    }
    if args.dfs_location_name:
        cfg["dataforseo"]["location_name"] = args.dfs_location_name
    return cfg


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Scaffold a single project pack (project.config.json).",
    )
    ap.add_argument("--project", required=True,
                    help="Lowercase kebab-case slug (matches projects/{slug}/).")
    ap.add_argument("--display-name", default=None)
    ap.add_argument("--domain", default="https://example.com/",
                    help="Project root URL (used as default gsc.site_url).")
    ap.add_argument("--market", default="TR",
                    help="ISO 3166-1 alpha-2 country code.")
    ap.add_argument("--locale", default="tr-TR",
                    help="IETF BCP 47 content locale.")
    ap.add_argument("--currency", default="TRY",
                    help="ISO 4217 currency code.")
    ap.add_argument(
        "--platform",
        default="wordpress",
        choices=["wordpress", "wordpress+woocommerce",
                 "ticimax", "ideasoft", "imagaza", "custom"],
    )
    ap.add_argument(
        "--platform-seo-plugin",
        default=None,
        choices=["rankmath", "yoast", "aioseo", "seopress", "none", None],
    )
    ap.add_argument(
        "--profile", action="append",
        choices=["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"],
        help="Repeatable; at least one is required (default: local-service).",
    )
    ap.add_argument("--ymyl-level", default="none",
                    choices=["none", "low", "medium", "high"])
    ap.add_argument("--gsc-site-url", default=None)
    ap.add_argument("--dfs-location-code", type=int, default=2792)
    ap.add_argument("--dfs-language-code", default="tr")
    ap.add_argument("--dfs-location-name", default=None)
    ap.add_argument("--out", default=None,
                    help="Override output path; default: projects/{slug}/project.config.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print JSON to stdout and exit; no files written.")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing project.config.json.")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    cfg = build_project_config(args)

    if args.dry_run:
        json.dump(cfg, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.out:
        out_path = Path(args.out).expanduser()
    else:
        projects_dir = Path(os.getenv("PSEO_PROJECTS_DIR") or "projects")
        out_path = projects_dir / args.project / "project.config.json"

    if out_path.exists() and not args.force:
        log(f"refusing to overwrite {out_path} (use --force)")
        return 2

    try:
        write_json(out_path, cfg)
    except OSError as e:
        log(f"write failed: {e}")
        return 1

    log(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
