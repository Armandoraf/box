import asyncio
import json
import os
import urllib.parse
import urllib.request
import unicodedata

import websockets


def _json_get(url: str) -> object:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _open_tab(port: int, url: str) -> None:
    endpoint = f"http://localhost:{port}/json/new?" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(endpoint, method="PUT")
    with urllib.request.urlopen(req, timeout=5):
        return


def _normalize_link(link: str) -> str:
    try:
        parsed = urllib.parse.urlparse(link)
    except Exception:
        return link

    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    drop_keys = {
        "srsltid",
        "ved",
        "ei",
        "oq",
        "gs_lcp",
        "gs_lp",
        "gs_ssp",
        "gs_a",
        "gs_ai",
        "sourceid",
        "ie",
        "usg",
    }
    filtered = [(k, v) for k, v in query if k not in drop_keys]
    new_query = urllib.parse.urlencode(filtered, doseq=True)
    cleaned = parsed._replace(query=new_query, fragment="")
    return urllib.parse.urlunparse(cleaned)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.strip()


async def _navigate_and_extract(ws_url: str, url: str) -> list[dict]:
    msg_id = 0

    async def send_cmd(ws, method: str, params: dict | None = None) -> dict:
        nonlocal msg_id
        msg_id += 1
        payload = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params
        await ws.send(json.dumps(payload))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == msg_id:
                return msg

    async with websockets.connect(ws_url) as ws:
        await send_cmd(ws, "Runtime.enable")
        await send_cmd(ws, "Page.enable")

        await send_cmd(ws, "Page.navigate", {"url": url})

        for _ in range(200):
            msg = json.loads(await ws.recv())
            if msg.get("method") == "Page.loadEventFired":
                break

        async def has_results() -> bool:
            check_js = """
(() => {
  if (location.href.includes('consent.google.com')) return false;
  const h3s = document.querySelectorAll('a h3');
  const newsCards = document.querySelectorAll('div.dbsr, article, g-card');
  const headings = document.querySelectorAll('[role=\"heading\"], .nDgy9d, .JheGif');
  return h3s.length > 0 || newsCards.length > 0 || headings.length > 0;
})();
"""
            resp = await send_cmd(
                ws,
                "Runtime.evaluate",
                {"expression": check_js, "returnByValue": True},
            )
            return bool(resp.get("result", {}).get("result", {}).get("value", False))

        for _ in range(30):
            if await has_results():
                break
            await asyncio.sleep(0.5)

        js = """
(() => {
  const isNews = new URLSearchParams(location.search).get('tbm') === 'nws';

  const pickSnippet = (root, t, src, ts) => {
    const candidates = Array.from(
      root.querySelectorAll(
        '.Y3v8qd, .GI74Re, .st, .VwiC3b, .aCOpRe, .r025kc, .WWztTb'
      )
    );
    let best = '';
    for (const el of candidates) {
      if (el.closest('.CEMjEf')) continue;
      const s = el.textContent?.trim() || '';
      if (!s || s === t || s === src || s === ts) continue;
      if (s.length > best.length) best = s;
    }
    if (best) return best;

    const lines = (root.innerText || '')
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);
    const filtered = lines.filter((l) => l !== t && l !== src && l !== ts);
    let fallback = '';
    for (const line of filtered) {
      if (line.length > fallback.length) fallback = line;
    }
    return fallback;
  };

  if (isNews) {
    const results = [];
    const cards = Array.from(document.querySelectorAll('div.dbsr'));
    for (const card of cards) {
      const a = card.querySelector('a');
      const title = card.querySelector('.JheGif, .nDgy9d');
      const source = card.querySelector('.CEMjEf span');
      const time = card.querySelector('time');
      if (!a || !title) continue;
      const link = a.getAttribute('href') || '';
      const t = title.textContent?.trim() || '';
      const src = source ? (source.textContent?.trim() || '') : '';
      const ts = time ? (time.textContent?.trim() || '') : '';
      const s = pickSnippet(card, t, src, ts);
      if (t && link) results.push({ title: t, link, snippet: s, source: src, time: ts });
    }
    if (results.length > 0) return results;

    const fallback = [];
    const anchors = Array.from(document.querySelectorAll('#search a, #rso a'));
    for (const a of anchors) {
      const title = a.querySelector('h3, [role=\"heading\"], .nDgy9d, .JheGif, .mCBkyc');
      const root = a.closest('article, g-card, div') || a;
      if (!title) continue;
      const link = a.getAttribute('href') || '';
      const t = title.textContent?.trim() || '';
      const s = pickSnippet(root, t, '', '');
      if (t && link) fallback.push({ title: t, link, snippet: s });
    }
    return fallback;
  }

  const blocks = Array.from(
    document.querySelectorAll('div#search div.MjjYud, div#search div.g, div#search .tF2Cxc')
  );
  const results = [];
  for (const g of blocks) {
    const title = g.querySelector('h3');
    const a = title ? title.closest('a') : g.querySelector('a');
    const snippet = g.querySelector('.VwiC3b, .IsZvec, .aCOpRe, .lyLwlc, .MUxGbd');
    if (!a || !title) continue;
    const link = a.getAttribute('href') || '';
    const t = title.textContent?.trim() || '';
    const s = snippet ? (snippet.textContent?.trim() || '') : '';
    if (t && link) results.push({ title: t, link, snippet: s });
  }
  if (results.length > 0) return results;

  const fallback = [];
  const h3s = Array.from(document.querySelectorAll('div#search a h3, a h3'));
  for (const h3 of h3s) {
    const a = h3.closest('a');
    if (!a) continue;
    const link = a.getAttribute('href') || '';
    const t = h3.textContent?.trim() || '';
    if (t && link) fallback.push({ title: t, link, snippet: '' });
  }
  return fallback;
})();
"""

        resp = await send_cmd(
            ws,
            "Runtime.evaluate",
            {"expression": js, "returnByValue": True},
        )
        result = resp.get("result", {}).get("result", {}).get("value", [])
        if isinstance(result, list):
            dedup: dict[str, dict] = {}
            ordered: list[str] = []
            for item in result:
                if not isinstance(item, dict):
                    continue
                link = item.get("link") or ""
                title = _normalize_text(item.get("title") or "")
                snippet = _normalize_text(item.get("snippet") or "")
                if not link or not title:
                    continue
                norm_link = _normalize_link(link)
                existing = dedup.get(norm_link)
                if not existing:
                    dedup[norm_link] = {
                        "title": title,
                        "link": link,
                        "snippet": snippet,
                    }
                    ordered.append(norm_link)
                    continue
                if len(snippet) > len(existing.get("snippet", "")):
                    dedup[norm_link]["snippet"] = snippet
            return [dedup[link] for link in ordered]
        return []


def search_google(query: str, news: bool = False, chrome_debug_port: int | None = None) -> dict:
    url = (
        "https://www.google.com/search?q="
        + urllib.parse.quote_plus(query)
        + "&hl=en&gl=us"
    )
    if news:
        url += "&tbm=nws"

    port = chrome_debug_port or int(os.environ.get("CHROME_DEBUG_PORT", "9225"))
    list_url = f"http://localhost:{port}/json/list"

    targets = _json_get(list_url)
    page = next((t for t in targets if t.get("type") == "page"), None)
    if not page or not page.get("webSocketDebuggerUrl"):
        _open_tab(port, url)
        targets = _json_get(list_url)
        page = next((t for t in targets if t.get("type") == "page"), None)
        if not page or not page.get("webSocketDebuggerUrl"):
            raise RuntimeError("No existing page target found. Open a tab first.")

    results = asyncio.run(_navigate_and_extract(page["webSocketDebuggerUrl"], url))
    return {"query": query, "url": url, "results": results}
