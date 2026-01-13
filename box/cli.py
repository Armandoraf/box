#!/usr/bin/env python3
import argparse
import json
import sys

from box.fetch import DEFAULT_USER_AGENT, build_headers, fetch
from box.search import search_google


def _fetch_cmd(args: argparse.Namespace) -> int:
    headers = build_headers(args.user_agent, args.accept_language)
    try:
        payload = fetch(args.url, args.timeout, headers, args.raw, args.raw_text)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "url": args.url}), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _search_cmd(args: argparse.Namespace) -> int:
    try:
        payload = search_google(args.query)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "query": args.query}), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal CLI for box")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_parser = sub.add_parser("fetch", help="Fetch a URL")
    fetch_parser.add_argument("url", help="URL to fetch")
    fetch_parser.add_argument("--timeout", type=float, default=20.0)
    fetch_parser.add_argument("--accept-language", default="en-US,en;q=0.9")
    fetch_parser.add_argument(
        "--raw",
        action="store_true",
        help="Include raw HTML in output (disabled by default).",
    )
    fetch_parser.add_argument(
        "--raw-text",
        action="store_true",
        help="Include raw text extraction in output (disabled by default).",
    )
    fetch_parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    fetch_parser.set_defaults(func=_fetch_cmd)

    search_parser = sub.add_parser("search", help="Search via Custom Search API")
    search_parser.add_argument("query", help="Search query")
    search_parser.set_defaults(func=_search_cmd)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
