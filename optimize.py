"""
Module d'optimisation automatique compatible Python 3.12+
"""

import json
import os
import shutil
from PIL import Image
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

from css_html_js_minify import html_minify, css_minify, js_minify


def _download_file(url, dest):
    try:
        r = requests.get(url, timeout=10, stream=True)
        if r.status_code == 200:
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        return False
    except:
        return False


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def run_optimization(analysis_report: dict, output_dir="optimized/"):
    """
    Optimise images, CSS, JS, HTML avec compatibilité full Python 3.12+
    """
    # Accept URL string or path to report JSON
    if isinstance(analysis_report, str):
        # URL -> perform live analysis
        if analysis_report.startswith(("http://", "https://")):
            try:
                from analysis import run_analysis as _run_analysis
                analysis_report = _run_analysis(analysis_report)
            except Exception as e:
                raise RuntimeError(f"failed to run analysis for URL {analysis_report}: {e}")
        # existing JSON file -> load
        elif os.path.exists(analysis_report):
            with open(analysis_report, "r", encoding="utf-8") as f:
                analysis_report = json.load(f)
        else:
            raise ValueError("analysis_report is a string but not a URL nor an existing file path")

    _ensure_dir(output_dir)
    img_dir = os.path.join(output_dir, "img")
    css_dir = os.path.join(output_dir, "css")
    js_dir = os.path.join(output_dir, "js")
    html_dir = os.path.join(output_dir, "html")

    for d in (img_dir, css_dir, js_dir, html_dir):
        _ensure_dir(d)


    # Download main HTML (if URL available) and save minified version
    main_url = analysis_report.get("url")
    main_html_content = None
    if main_url:
        try:
            resp = requests.get(main_url, timeout=15)
            if resp.status_code == 200:
                main_html_content = resp.text
                minified = html_minify(main_html_content)
                with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
                    f.write(minified)
        except Exception:
            main_html_content = None

    # If css_js list is empty, try to extract CSS/JS links from the downloaded HTML
    if not analysis_report.get("css_js") and main_html_content:
        try:
            soup = BeautifulSoup(main_html_content, "html.parser")
            found = []
            for link in soup.find_all("link", rel="stylesheet"):
                href = link.get("href")
                if href:
                   found.append({"url": urljoin(main_url, href), "type": "stylesheet"})
            for script in soup.find_all("script"):
                src = script.get("src")
                if src:
                    found.append({"url": urljoin(main_url, src), "type": "script"})
            if found:
                analysis_report["css_js"] = found
        except Exception:
            pass


    result = {
        "images": [],
        "minified": [],
        "removed": [],
        "summary": {},
    }

    # ----------------------------------------------------------
    # 1) Optimisation images (WebP + AVIF)
    # ----------------------------------------------------------
    for img in analysis_report.get("images", []):
        src = img.get("src")
        if not src or src.startswith("data:"):
            continue

        filename = os.path.basename(urlparse(src).path)
        if not filename:
            continue

        original_path = os.path.join(img_dir, filename)

        if not _download_file(src, original_path):
            continue

        try:
            im = Image.open(original_path).convert("RGB")

            webp_path = original_path + ".webp"
            avif_path = original_path + ".avif"

            im.save(webp_path, "webp", quality=80)
            im.save(avif_path, "avif", quality=35)

            result["images"].append({
                "src": src,
                "original": original_path,
                "webp": webp_path,
                "avif": avif_path,
                "gain_webp": os.path.getsize(original_path) - os.path.getsize(webp_path),
                "gain_avif": os.path.getsize(original_path) - os.path.getsize(avif_path),
            })
        except Exception as e:
            result["images"].append({"src": src, "error": str(e)})

    # ----------------------------------------------------------
    # 2) Minification CSS / JS
    # ----------------------------------------------------------
    for res in analysis_report.get("css_js", []):
        url = res.get("url")
        rtype = res.get("type")

        filename = os.path.basename(urlparse(url).path)
        if not filename:
            continue

        dest = os.path.join(css_dir if rtype == "stylesheet" else js_dir, filename)

        if not _download_file(url, dest):
            continue

        with open(dest, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if rtype == "stylesheet":
            optimized = css_minify(content)
        elif rtype == "script":
            optimized = js_minify(content)
        else:
            continue

        with open(dest, "w", encoding="utf-8") as f:
            f.write(optimized)

        result["minified"].append({
            "url": url,
            "file": dest,
            "original_size": len(content.encode("utf-8")),
            "optimized_size": len(optimized.encode("utf-8"))
        })

    # ----------------------------------------------------------
    # 3) Suppression fichiers inutiles
    # ----------------------------------------------------------
    result["removed"] = analysis_report.get("dead_css", []) + analysis_report.get("dead_js", [])

    # ----------------------------------------------------------
    # 4) Résumé
    # ----------------------------------------------------------
    total_gain = sum(
        (img.get("gain_webp", 0) + img.get("gain_avif", 0))
        for img in result["images"]
    )

    result["summary"] = {
        "total_images_optimized": len(result["images"]),
        "total_files_minified": len(result["minified"]),
        "total_unused_removed": len(result["removed"]),
        "total_gain_bytes": total_gain
    }

    return result
