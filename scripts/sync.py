#!/usr/bin/env python3
"""Pull the public Casa Stellare site and rebuild the static pages.

WordPress admin, WooCommerce orders, and the TIFF masters are not part of
this pull. Re-run after the live site changes:

    python3 scripts/sync.py
"""

import html
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "media" / "uploads"
CONTENT = ROOT / "content"
ORIGIN = "https://casastellare.com"
UA = {"User-Agent": "CasaStellareLocal/1.0"}

PAGES = {
    "home": f"{ORIGIN}/",
    "observatory": f"{ORIGIN}/?page_id=2",
    "pier1": f"{ORIGIN}/?page_id=84",
    "pier2": f"{ORIGIN}/?page_id=180",
    "about": f"{ORIGIN}/?page_id=373",
    "lake": f"{ORIGIN}/?page_id=602",
}

NAV = [
    ("index.html", "Home", "home"),
    ("observatory.html", "Observatory", "observatory"),
    ("pier-1.html", "Pier 1", "pier1"),
    ("pier-2.html", "Pier 2", "pier2"),
    ("about.html", "About", "about"),
    ("lake.html", "N11", "lake"),
]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def textify(raw):
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw).replace("\xa0", " ")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n+", "\n", raw)
    return raw.strip()


def prettify(name):
    name = re.sub(r"^\d+[A-Za-z]?-", "", name)
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\bSH2(?=\d)", "SH2-", name)
    name = re.sub(r"\b(NGC|IC|VDB)(?=\d)", r"\1 ", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def looks_technical(name):
    return bool(re.match(r"^(\d|IMG|img|Obs|Back|Scope|N11|set)", name or ""))


def local_for(url):
    path = url.split("?", 1)[0]
    marker = "/wp-content/uploads/"
    if marker not in path:
        return None
    rel = path.split(marker, 1)[1]
    return "media/uploads/" + rel


def item_from_gallery(href, title, description):
    title = textify(title)
    description = textify(description)
    text = ""
    if description and looks_technical(title) and description != title:
        if len(description.split()) > 8:
            title = prettify(title)
            text = description
        else:
            title = description
    elif looks_technical(title):
        pretty = prettify(title)
        title = "" if re.match(r"^(IMG|Obs|Back|Scope)", pretty, re.I) else pretty
    elif description and description != title:
        text = description
    if re.match(r"(?i)^set\s*\d+$", title):
        title = re.sub(r"(?i)^set\s*", "Set ", title)
    return {
        "src": href,
        "local": local_for(href),
        "title": title,
        "text": text,
    }


def elementor_gallery(page_html):
    items = []
    for match in re.finditer(
        r'<a class="e-gallery-item[^"]*" href="([^"]+)"[^>]*data-elementor-lightbox-title="([^"]*)"(.*?)</a>',
        page_html,
        re.S,
    ):
        desc = re.search(
            r'elementor-gallery-item__description">\s*(.*?)\s*</div>',
            match.group(3),
            re.S,
        )
        items.append(item_from_gallery(match.group(1), match.group(2), desc.group(1) if desc else ""))
    return items


def featured_gallery(page_html):
    items = []
    for match in re.finditer(
        r'class="eael-gallery-grid-item"><a[^>]*href="([^"]+)"[\s\S]*?<h2 class="fg-item-title">(.*?)</h2>[\s\S]*?<div class="fg-item-content">([\s\S]*?)</div>',
        page_html,
    ):
        entry = item_from_gallery(match.group(1), match.group(2), "")
        entry["text"] = textify(match.group(3))
        entry["title"] = textify(match.group(2))
        items.append(entry)
    return items


def parse(pages):
    home = pages["home"]
    strips = []
    for alt, src in re.findall(r'<img[^>]+class="swiper-slide-image"[^>]+alt="([^"]*)"[^>]+src="([^"]+)"', home):
        label = textify(alt)
        if re.match(r"(?i)^set\s*\d+", label):
            label = re.sub(r"(?i)^set\s*", "Set ", label)
        strips.append({"src": src, "local": local_for(src), "title": label})
    if not strips:
        for src, alt in re.findall(r'<img[^>]+class="swiper-slide-image"[^>]+src="([^"]+)"[^>]+alt="([^"]*)"', home):
            label = textify(alt)
            if re.match(r"(?i)^set\s*\d+", label):
                label = re.sub(r"(?i)^set\s*", "Set ", label)
            strips.append({"src": src, "local": local_for(src), "title": label})
    banner_url = None
    banner_match = re.search(r'src="(https://casastellare.com/wp-content/uploads/[^"]*BannerThin[^"]+)"', home)
    if banner_match:
        banner_url = banner_match.group(1)
    latest_srcs = re.findall(
        r'src="(https://casastellare.com/wp-content/uploads/2022/12/[^"]+)"',
        home,
    )
    seen = []
    latest = []
    for src in latest_srcs:
        full = re.sub(r"-\d+x\d+(?=\.(?:jpg|jpeg|png)$)", "", src)
        if full in seen:
            continue
        seen.append(full)
        latest.append({"src": full, "local": local_for(full), "title": prettify(Path(full).stem)})
    intro = ""
    intro_match = re.search(r'elementor-image-box-description">(.*?)</p>', home, re.S)
    if intro_match:
        intro = textify(intro_match.group(1))

    about_html = pages["about"]
    people = []
    chunks = re.findall(
        r'<img[^>]+src="(https://casastellare.com/wp-content/uploads/[^"]+)"[^>]*>[\s\S]*?<figcaption[^>]*>(.*?)</figcaption>[\s\S]*?<p[^>]*>(.*?)</p>',
        about_html,
    )
    for src, name, bio in chunks:
        people.append({
            "src": src,
            "local": local_for(src),
            "name": textify(name),
            "bio": textify(bio),
        })
    about_intro = []
    for part in re.findall(r"<p[^>]*>(.*?)</p>", about_html, re.S):
        cleaned = textify(part)
        if cleaned.startswith("The Casa Stellare team") or cleaned.startswith("We hope you enjoy"):
            about_intro.append(cleaned)

    lake_html = pages["lake"]
    headings = [textify(h) for h in re.findall(r'elementor-heading-title[^>]*>(.*?)</h2>', lake_html, re.S)]

    return {
        "pulled_from": ORIGIN,
        "banner": {"src": banner_url, "local": local_for(banner_url) if banner_url else None},
        "home": {"intro": intro, "strips": strips, "latest": latest[:3]},
        "pier1": {
            "featured": featured_gallery(pages["pier1"]),
            "gallery": elementor_gallery(pages["pier1"]),
        },
        "pier2": {"gallery": elementor_gallery(pages["pier2"])},
        "observatory": {"gallery": elementor_gallery(pages["observatory"])},
        "about": {"intro": about_intro, "people": people},
        "lake": {
            "title": headings[0] if headings else "N11",
            "credit": headings[1] if len(headings) > 1 else "",
            "gallery": elementor_gallery(lake_html),
        },
    }


def collect_urls(site):
    urls = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("src"):
                urls.add(node["src"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(site)
    return urls


def download(url):
    rel = local_for(url)
    if not rel:
        raise RuntimeError(f"not an upload: {url}")
    dest = ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return rel, dest.stat().st_size, False
    data = get(url)
    dest.write_bytes(data)
    return rel, len(data), True


def fetch_library():
    items = []
    page = 1
    while True:
        try:
            payload = json.loads(get(
                f"{ORIGIN}/index.php?rest_route=/wp/v2/media&per_page=50&page={page}"
                "&_fields=id,title,caption,alt_text,source_url,mime_type,media_details"
            ))
        except urllib.error.HTTPError as error:
            if error.code == 400 and page > 1:
                break
            raise
        if not payload:
            break
        for media in payload:
            if not str(media.get("mime_type", "")).startswith("image/"):
                continue
            details = media.get("media_details") or {}
            items.append({
                "id": media["id"],
                "title": textify((media.get("title") or {}).get("rendered", "")),
                "caption": textify((media.get("caption") or {}).get("rendered", "")),
                "alt": media.get("alt_text") or "",
                "src": media.get("source_url"),
                "local": local_for(media.get("source_url") or ""),
                "width": details.get("width"),
                "height": details.get("height"),
                "mime": media.get("mime_type"),
            })
        page += 1
    return items


def esc(value):
    return html.escape(value or "", quote=True)


def figure(entry, essay=False):
    src = entry["local"] or entry["src"]
    title = entry.get("title") or ""
    text = entry.get("text") or ""
    if essay:
        body = f"<h2>{esc(title)}</h2>"
        if text:
            body += f"<p>{esc(text)}</p>"
        return (
            "<figure class=\"essay\">"
            f"<button class=\"essay-open\" type=\"button\" data-full=\"{esc(src)}\">"
            f"<img src=\"{esc(src)}\" alt=\"{esc(title)}\"></button>"
            f"<figcaption>{body}</figcaption></figure>"
        )
    label = f"<span>{esc(title)}</span>" if title else ""
    return (
        "<figure>"
        f"<button class=\"shot\" type=\"button\" data-full=\"{esc(src)}\">"
        f"<img src=\"{esc(src)}\" alt=\"{esc(title)}\" loading=\"lazy\">{label}</button>"
        "</figure>"
    )


def layout(active, title, body, description):
    links = []
    for href, label, key in NAV:
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<a href="{href}"{current}>{label}</a>')
    banner = "media/uploads/2026/11/BannerThinSubtitledMy.png"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="icon" href="media/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/site.css">
</head>
<body>
  <a class="skip" href="#content">Skip to content</a>
  <header class="site-header">
    <a href="index.html"><img class="banner" src="{banner}" alt="Casa Stellare, astrophotography from our remote observatory"></a>
    <nav class="nav" aria-label="Pages">{''.join(links)}</nav>
  </header>
  <main id="content">
{body}
  </main>
  <footer class="site-footer">Jeff McFarlin, Jerry Smith, and Josh Lake.</footer>
  <dialog class="lightbox" aria-label="Image">
    <div class="lightbox-bar">
      <span>Casa Stellare</span>
      <button type="button" data-close>Close</button>
    </div>
    <div class="lightbox-stage">
      <button class="lightbox-nav" type="button" data-prev aria-label="Previous image">Prev</button>
      <img alt="">
      <button class="lightbox-nav" type="button" data-next aria-label="Next image">Next</button>
    </div>
    <p class="lightbox-caption"></p>
  </dialog>
  <script src="js/strips.js"></script>
  <script src="js/gallery.js"></script>
</body>
</html>
"""


def strip_row():
    root = ROOT / "media" / "strips"
    columns = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: int(p.name)) if root.is_dir() else []
    if len(columns) != 6:
        return ""
    panels = []
    for column in columns:
        frames = sorted(column.glob("*.png"))
        imgs = "\n".join(
            f'      <img src="media/strips/{column.name}/{frame.name}" alt="">'
            for frame in frames
        )
        panels.append(f"    <div class=\"panel\">\n{imgs}\n    </div>")
    return "<div class=\"strip-row\">\n" + "\n".join(panels) + "\n    </div>"


def render(site):
    home_strips = strip_row()
    home_latest = "\n".join(figure(item, essay=True) for item in site["home"]["latest"])
    (ROOT / "index.html").write_text(layout(
        "home",
        "Casa Stellare",
        f"""    {home_strips}
    <h1 class="section-title">Latest images</h1>
    <div class="lede"><p>{esc(site["home"]["intro"])}</p></div>
    <div class="essays" data-gallery>
{home_latest}
    </div>""",
        "Astrophotography from our remote observatory.",
    ))

    pier1 = site["pier1"]
    (ROOT / "pier-1.html").write_text(layout(
        "pier1",
        "Pier 1 Gallery — Casa Stellare",
        f"""    <h1>Pier 1</h1>
    <div class="essays" data-gallery>
{chr(10).join(figure(item, essay=True) for item in pier1["featured"])}
    </div>
    <h2 class="section-title">The rest of the pier</h2>
    <div class="grid" data-gallery>
{chr(10).join(figure(item) for item in pier1["gallery"])}
    </div>""",
        "Images from the first pier at Casa Stellare.",
    ))

    (ROOT / "pier-2.html").write_text(layout(
        "pier2",
        "Pier 2 Gallery — Casa Stellare",
        f"""    <h1>Pier 2</h1>
    <div class="grid" data-gallery>
{chr(10).join(figure(item) for item in site["pier2"]["gallery"])}
    </div>""",
        "Images from the second pier at Casa Stellare.",
    ))

    (ROOT / "observatory.html").write_text(layout(
        "observatory",
        "Observatory — Casa Stellare",
        f"""    <h1>Observatory</h1>
    <div class="grid" data-gallery>
{chr(10).join(figure(item) for item in site["observatory"]["gallery"])}
    </div>""",
        "The Casa Stellare remote observatory.",
    ))

    people = "\n".join(
        f"""<article>
        <img src="{esc(person["local"])}" alt="{esc(person["name"])}">
        <h2>{esc(person["name"])}</h2>
        <p>{esc(person["bio"])}</p>
      </article>"""
        for person in site["about"]["people"]
    )
    intro = "\n".join(f"<p>{esc(part)}</p>" for part in site["about"]["intro"])
    (ROOT / "about.html").write_text(layout(
        "about",
        "About — Casa Stellare",
        f"""    <h1>About us</h1>
    <div class="lede">{intro}</div>
    <div class="people">
{people}
    </div>""",
        "Jeff McFarlin, Jerry Smith, and Josh Lake.",
    ))

    lake = site["lake"]
    credit = esc(lake["credit"]).replace("\n", "<br>")
    (ROOT / "lake.html").write_text(layout(
        "lake",
        "N11 — Casa Stellare",
        f"""    <h1>{esc(lake["title"])}</h1>
    <p class="credit">{credit}</p>
    <div class="essays" data-gallery>
{chr(10).join(figure(item, essay=True) for item in lake["gallery"])}
    </div>""",
        lake["title"],
    ))


def main():
    print("fetching pages")
    pages = {name: get(url).decode("utf-8", "replace") for name, url in PAGES.items()}
    raw = CONTENT / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, page_html in pages.items():
        (raw / f"{name}.html").write_text(page_html)

    print("fetching media library")
    library = fetch_library()
    site = parse(pages)
    urls = collect_urls(site)
    for media in library:
        if media["src"]:
            urls.add(media["src"])
    urls.add(f"{ORIGIN}/wp-content/uploads/2022/02/Screen-Shot-2022-02-28-at-10.03.02-PM-100x100.png")

    print(f"downloading {len(urls)} images")
    downloaded = 0
    total = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(download, url) for url in sorted(urls)]
        for future in as_completed(futures):
            rel, size, fresh = future.result()
            total += size
            if fresh:
                downloaded += 1
    favicon_src = ROOT / "media/uploads/2022/02/Screen-Shot-2022-02-28-at-10.03.02-PM-100x100.png"
    favicon = ROOT / "media/favicon.png"
    if favicon_src.exists():
        favicon.write_bytes(favicon_src.read_bytes())

    CONTENT.mkdir(parents=True, exist_ok=True)
    (CONTENT / "site.json").write_text(json.dumps(site, indent=2) + "\n")
    (CONTENT / "media.json").write_text(json.dumps(library, indent=2) + "\n")
    render(site)
    print(f"images touched: {len(urls)}  newly downloaded: {downloaded}  bytes: {total}")
    print(f"pier 1 featured {len(site['pier1']['featured'])} gallery {len(site['pier1']['gallery'])}")
    print(f"pier 2 {len(site['pier2']['gallery'])} observatory {len(site['observatory']['gallery'])}")
    print(f"about people {len(site['about']['people'])} lake {len(site['lake']['gallery'])}")
    print(f"library records {len(library)}")


if __name__ == "__main__":
    main()
