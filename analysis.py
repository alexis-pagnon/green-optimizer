"""
Module d'analyse pour le projet Green Optimizer.

Fonction principale : run_analysis(url) → dict
"""

import time
from typing import Dict, Any, List
from urllib.parse import urljoin

def _detect_unused_images(page, network_events: List[Dict[str, Any]], images: List[Dict[str, Any]], base_url: str) -> List[str]:
    """
    Return list of image URLs that were loaded (network events) but not used in DOM <img>
    nor referenced as CSS background-images. Also include DOM images with zero natural size.
    Heuristic: compare absolute URLs.
    """
    try:
        net_images = set(
            ne.get("url") for ne in network_events
            if ne.get("resource_type") == "image" and ne.get("url")
        )
        # absolute srcs from DOM images collected
        dom_abs = set()
        zero_dom = set()
        for img in images:
            src = img.get("src") or ""
            abs_src = img.get("absolute_src") or (urljoin(base_url, src) if src else "")
            if abs_src:
                dom_abs.add(abs_src)
                if (not img.get("width") or not img.get("height")):
                    zero_dom.add(abs_src)

        # collect CSS background-image URLs (absolute) in page
        try:
            bg_urls = page.evaluate(
                """() => {
                    const urls = new Set();
                    for (const el of document.querySelectorAll('*')) {
                        try {
                            const s = getComputedStyle(el).getPropertyValue('background-image');
                            if (!s || s === 'none') continue;
                            // match all url(...) occurrences
                            const re = /url\\((?:'|")?(.*?)(?:'|")?\\)/g;
                            let m;
                            while ((m = re.exec(s)) !== null) {
                                try {
                                    urls.add(new URL(m[1], location.href).href);
                                } catch(e){}
                            }
                        } catch(e){}
                    }
                    return Array.from(urls);
                }"""
            )
        except Exception:
            bg_urls = []

        used = dom_abs.union(set(bg_urls))
        dead = sorted(list(net_images - used))

        # include DOM zero-size images that were requested but not already in dead
        for z in sorted(zero_dom):
            if z not in dead and z in net_images:
                dead.append(z)

        return dead
    except Exception:
        return []

def _start_cdp_coverage(cdp) -> None:
    try:
        cdp.send("Profiler.enable")
        cdp.send("Profiler.startPreciseCoverage", {"callCount": False, "detailed": True})
    except Exception:
        pass
    try:
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        cdp.send("CSS.startRuleUsageTracking")
    except Exception:
        pass

def _stop_and_get_dead_files(cdp, network_events: List[Dict[str, Any]], unused_threshold: float = 0.7) -> List[str]:
    """
    Retourne une liste d'URLs de fichiers (JS/CSS) chargés mais majoritairement inutilisés.
    Seuil par défaut : 0.7 (>=70% unused => considéré "dead").
    """
    dead = []
    try:
        # JS coverage
        js_cov = None
        try:
            js_cov = cdp.send("Profiler.takePreciseCoverage")
            cdp.send("Profiler.stopPreciseCoverage")
        except Exception:
            js_cov = None

        if js_cov and "result" in js_cov:
            for entry in js_cov["result"]:
                url = entry.get("url") or ""
                if not url:
                    continue
                total = 0
                used = 0
                for func in entry.get("functions", []):
                    for r in func.get("ranges", []):
                        length = max(0, r.get("endOffset", 0) - r.get("startOffset", 0))
                        total += length
                        if r.get("count", 0) > 0:
                            used += length
                if total > 0:
                    unused_pct = 1.0 - (used / total)
                    if unused_pct >= unused_threshold:
                        dead.append(url)

        # CSS coverage
        css_cov = None
        try:
            css_cov = cdp.send("CSS.stopRuleUsageTracking")
        except Exception:
            css_cov = None

        if css_cov and "ruleUsage" in css_cov:
            # aggregate by styleSheetId
            css_map = {}
            for ru in css_cov.get("ruleUsage", []):
                sid = ru.get("styleSheetId")
                used = bool(ru.get("used", False))
                start = ru.get("startOffset", 0)
                end = ru.get("endOffset", 0)
                length = max(0, end - start)
                if sid not in css_map:
                    css_map[sid] = {"total_ranges": 0, "used_ranges": 0}
                css_map[sid]["total_ranges"] += length
                if used:
                    css_map[sid]["used_ranges"] += length

            for sid, vals in css_map.items():
                try:
                    txt = cdp.send("CSS.getStyleSheetText", {"styleSheetId": sid}).get("text", "") or ""
                    total_real = len(txt.encode("utf-8"))
                    used_bytes = vals.get("used_ranges", 0)
                    unused_pct = 1.0 - (used_bytes / total_real) if total_real > 0 else 0.0

                    # heuristique pour retrouver l'URL : rechercher fichier .css dans les network_events contenu dans le texte
                    url_guess = None
                    for ne in network_events:
                        ne_url = ne.get("url")
                        if not ne_url:
                            continue
                        if ne_url.endswith(".css") and (ne_url.split("/")[-1] in txt or abs((ne.get("body_size") or 0) - total_real) < 20):
                            url_guess = ne_url
                            break

                    if url_guess and unused_pct >= unused_threshold:
                        dead.append(url_guess)
                except Exception:
                    # si impossible d'obtenir texte, on skip
                    pass

    except Exception:
        pass

    # dédupliquer et retourner
    return list(dict.fromkeys(dead))

def run_analysis(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Orchestrateur : essaie d'utiliser Playwright.
    Si Playwright n'est pas disponible → fallback simple (requests + BeautifulSoup).
    """
    report = {
        "url": url,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {},
        "requests": [],
        "images": [],
        "css_js": [],
        "notes": [],
    }

    # --------------------------------
    # TENTER PLAYWRIGHT
    # --------------------------------
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        report["notes"].append(f"playwright_not_available: {e}")
        #  return _fallback_requests_analysis(url, report)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            network_events = []

            def on_response(response):
                try:
                    entry = {
                        "url": response.url,
                        "status": response.status,
                        "resource_type": response.request.resource_type,
                        "headers": dict(response.headers),
                    }

                    # Taille du body si possible
                    try:
                        body = response.body()
                        entry["body_size"] = len(body)
                    except:
                        entry["body_size"] = None

                    network_events.append(entry)
                except:
                    pass

            page.on("response", on_response)
# start CDP coverage if possible (to detect unused files)
            cdp = None
            try:
                cdp = context.new_cdp_session(page)
                _start_cdp_coverage(cdp)
            except Exception:
                cdp = None

            page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
            page.wait_for_timeout(1000)

            # stop coverage and compute dead files list (if cdp available)
            dead_files = []
            if cdp:
                try:
                    dead_files = _stop_and_get_dead_files(cdp, network_events, unused_threshold=0.7)
                except Exception:
                    dead_files = []
            report["dead_files"] = dead_files

            # Collecter les images du DOM
            dom_images = page.query_selector_all("img")
            images = []
            base_url = page.url or url
            for img in dom_images:
                try:
                    src = img.get_attribute("src")
                    abs_src = urljoin(base_url, src) if src else None
                    dims = page.evaluate(
                        "(el) => ({w: el.naturalWidth, h: el.naturalHeight})", img
                    )
                    images.append({
                        "src": src,
                        "absolute_src": abs_src,
                        "width": dims.get("w"),
                        "height": dims.get("h"),
                    })
                except:
                    images.append({"src": None, "absolute_src": None})

            # Résumé
            total_transfer = 0
            reqs_out = []

            for r in network_events:
                size = r.get("body_size") or int(r["headers"].get("content-length", 0))
                total_transfer += size

                reqs_out.append({
                    "url": r["url"],
                    "status": r["status"],
                    "resource_type": r["resource_type"],
                    "transfer_size": size,
                })

            # CSS/JS
            css_js = [
                {
                    "url": r["url"],
                    "type": r["resource_type"],
                    "size": r["transfer_size"],
                }
                for r in reqs_out
                if r["resource_type"] in ("stylesheet", "script")
            ]

            dead_images = _detect_unused_images(page, network_events, images, base_url)
            report["dead_images"] = dead_images
            # add summary count
            report["summary"]
            # Populate report
            report["images"] = images
            report["requests"] = reqs_out
            report["css_js"] = css_js

            
            report["summary"] = {
                "total_requests": len(reqs_out),
                "total_transfer_bytes": total_transfer,
                "total_images": len(images),
                "total_css_js_files": len(css_js),
                "dead_images_count": len(dead_images)
            }

            report["notes"].append("analysis_via_playwright_OK")

            context.close()
            browser.close()
            return report

    except Exception as e:
        report["notes"].append(f"playwright_runtime_error: {e}")
        # return _fallback_requests_analysis(url, report)


# ---------------------------------------------
# FALLBACK : requests + BeautifulSoup
# ---------------------------------------------
# def _fallback_requests_analysis(url: str, base_report: Dict[str, Any]) -> Dict[str, Any]:
#     import requests
#     from bs4 import BeautifulSoup

#     try:
#         r = requests.get(url, timeout=20, headers={"User-Agent": "green-optimizer-bot"})
#         html = r.text
#         soup = BeautifulSoup(html, "html.parser")

#         images = [
#             {"src": img.get("src")}
#             for img in soup.find_all("img")
#         ]

#         css_js = []
#         for link in soup.find_all("link", rel="stylesheet"):
#             css_js.append({"url": link.get("href"), "type": "stylesheet"})

#         for script in soup.find_all("script"):
#             if script.get("src"):
#                 css_js.append({"url": script.get("src"), "type": "script"})

#         base_report["requests"] = [{
#             "url": url,
#             "status": r.status_code,
#             "resource_type": "document",
#             "transfer_size": len(r.content),
#         }]

#         base_report["images"] = images
#         base_report["css_js"] = css_js
#         base_report["summary"] = {
#             "total_requests": 1,
#             "total_transfer_bytes": len(r.content),
#             "total_images": len(images),
#             "total_css_js_files": len(css_js),
#             "dead_files_count": len(report.get("dead_files", []))
#         }
#         base_report["notes"].append("fallback_used (no playwright)")
#         return base_report

#     except Exception as e:
#         base_report["notes"].append(f"fallback_failed: {e}")
#         return base_report
