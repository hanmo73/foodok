#!/usr/bin/env python3
"""
foodok.org - static page generator.

Reads china.json, europe.json, korea.json from the repo root and writes
static HTML pages (origin country, food category, hazard, product topic and
country+category combinations), an /explore/ hub page, seo.css and
sitemap-pages.xml.

Run from the repo root:  python3 scripts/build_pages.py
Nothing here edits existing files (index.html, sitemap.xml, robots.txt ...).
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape

SITE = "https://foodok.org"
ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else ROOT

# ---- thresholds (keep pages from being thin) -------------------------------
MIN_ORIGIN = 10
MIN_COMBO = 15
MIN_PRODUCT = 10
MIN_TOPIC = 10
RECENT_ROWS = 40

SOURCES = {
    "china": ("China customs (GACC)", "China"),
    "eu": ("EU RASFF", "the EU"),
    "korea": ("South Korea MFDS", "South Korea"),
}

COUNTRY_FIX = {
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "united kingdom (northern ireland)": "United Kingdom",
    "viet nam": "Vietnam",
    "russian federation": "Russia",
}
SKIP_COUNTRY = {"", "unknown origin", "unknown", "not specified"}
SKIP_HAZARD = {"Not specified", "Other"}

TOPICS = [
    ("chili-pepper", "Chili and pepper",
     r"chil+i|capsicum|paprika|cayenne|(?<!black )(?<!white )\bpeppers?\b(?! ?corn)"),
    ("shrimp", "Shrimp and prawns", r"shrimp|prawn"),
    ("coffee", "Coffee", r"coffee"),
    ("tea", "Tea", r"\btea\b"),
    ("durian", "Durian", r"durian"),
    ("cashew-nuts", "Cashew nuts", r"cashew"),
    ("rice", "Rice", r"\brice\b"),
    ("honey", "Honey", r"\bhoney\b"),
    ("mango", "Mango", r"mango"),
    ("sesame-seeds", "Sesame seeds", r"sesame"),
    ("peanuts", "Peanuts", r"peanut|groundnut"),
    ("catfish-pangasius", "Pangasius and catfish", r"pangasius|catfish|\bbasa\b"),
    ("dried-fruit", "Dried fruit", r"dried (fig|apricot|fruit|mango|banana|date|raisin)|raisin|\bfigs?\b"),
    ("black-pepper", "Black and white pepper", r"black pepper|white pepper|peppercorn"),
    ("spices", "Spices and seasonings", r"spice|seasoning|cumin|turmeric|curry"),
]


# ---- helpers ---------------------------------------------------------------
def slugify(text):
    t = unicodedata.normalize("NFKD", text)
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60].strip("-")


def norm_country(c):
    c = (c or "").strip()
    return COUNTRY_FIX.get(c.lower(), c)


def parse_product(s):
    m = re.match(r"^(.*?) from ([^:]+):", s)
    if not m:
        return None
    p = m.group(1).strip()
    if not p or len(p) > 60:
        return None
    return p


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def write(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def n(x):
    return f"{x:,}"


def month_label(d):
    try:
        return datetime.strptime(d[:7], "%Y-%m").strftime("%b %Y")
    except ValueError:
        return d


# ---- load & normalise ------------------------------------------------------
def build_records():
    recs = []
    for r in load("china.json"):
        recs.append(dict(src="china", date=r["d"], text=r["s"], cat=r["f"],
                         origins=[norm_country(r["o"])], hazards=list(r["g"]),
                         product=parse_product(r["s"])))
    for r in load("europe.json"):
        recs.append(dict(src="eu", date=r["d"], text=r["s"], cat=r["f"],
                         origins=[norm_country(x) for x in r["o"]], hazards=list(r["g"]),
                         product=None))
    for r in load("korea.json"):
        recs.append(dict(src="korea", date=r["d"], text=r["s"], cat=r["f"],
                         origins=[norm_country(r["o"])], hazards=list(r["g"]),
                         product=parse_product(r["s"])))
    for r in recs:
        r["origins"] = [o for o in r["origins"] if o.lower() not in SKIP_COUNTRY]
        r["hazards_named"] = [h for h in r["hazards"] if h not in SKIP_HAZARD]
    return recs


# ---- HTML ------------------------------------------------------------------
CSS = """
:root{color-scheme:light;--bg:#f7f3e8;--ink:#1c1b19;--muted:#5d5a52;--line:#d9d3c1;--bar:#a8321f;--link:#0d4a86;--panel:#fffdf6}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--link)}
a:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.top{border-bottom:1px solid var(--line);background:var(--panel)}
.top div{max-width:860px;margin:0 auto;padding:12px 20px;display:flex;gap:20px;align-items:baseline}
.top .brand{font-weight:700;font-size:1.15rem;color:var(--ink);text-decoration:none;margin-right:auto}
.top a{text-decoration:none;color:var(--ink)}
.top a:hover{text-decoration:underline}
main{max-width:860px;margin:0 auto;padding:24px 20px 56px}
.crumbs{font-size:.88rem;color:var(--muted);margin:0 0 14px}
.crumbs a{color:var(--muted)}
h1{font:700 2rem/1.2 Georgia,"Times New Roman",serif;margin:0 0 14px;letter-spacing:-.01em}
h2{font:700 1.25rem/1.3 Georgia,"Times New Roman",serif;margin:36px 0 10px}
.lede{font-size:1.05rem;max-width:70ch;margin:0 0 6px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);font-size:.95rem}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;background:#efe9d6}
td.num,th.num{text-align:right;white-space:nowrap}
.scroll{overflow-x:auto}
.bar{display:block;height:8px;background:var(--bar);border-radius:2px;min-width:2px}
td.barcell{width:34%}
ul.links{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:8px 10px}
ul.links li a{display:inline-block;padding:4px 10px;border:1px solid var(--line);background:var(--panel);border-radius:4px;text-decoration:none}
ul.links li a:hover{border-color:var(--ink)}
.note{font-size:.88rem;color:var(--muted);margin-top:28px;max-width:70ch}
.date{white-space:nowrap;color:var(--muted)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.85rem}
footer div{max-width:860px;margin:0 auto;padding:18px 20px}
@media(max-width:600px){h1{font-size:1.6rem}td.barcell{display:none}th.barhead{display:none}}
"""


def page(title, desc, path, crumbs, body):
    canon = f"{SITE}{path}"
    crumb_html = " / ".join(
        f'<a href="{escape(u)}">{escape(t)}</a>' if u else escape(t) for t, u in crumbs)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{canon}">
<link rel="stylesheet" href="/seo.css">
</head>
<body>
<header class="top"><div><a class="brand" href="/">foodok</a><a href="/explore/">Explore</a></div></header>
<main>
<p class="crumbs">{crumb_html}</p>
{body}
</main>
<footer><div>foodok compiles public border notices from China customs (GACC), the EU RASFF portal and South Korea MFDS. It is not an official source. Check the original notice before you make a trade decision.</div></footer>
</body>
</html>
"""


def link_list(items):
    if not items:
        return ""
    lis = "".join(f'<li><a href="{escape(u)}">{escape(t)}</a></li>' for t, u in items)
    return f'<ul class="links">{lis}</ul>'


class Site:
    def __init__(self, recs):
        self.recs = recs
        self.today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.origin_idx = defaultdict(list)
        self.cat_idx = defaultdict(list)
        self.hazard_idx = defaultdict(list)
        self.combo_idx = defaultdict(list)
        self.product_idx = defaultdict(list)
        self.product_names = {}
        self.topic_idx = defaultdict(list)
        for r in recs:
            for o in set(r["origins"]):
                self.origin_idx[o].append(r)
                self.combo_idx[(o, r["cat"])].append(r)
            self.cat_idx[r["cat"]].append(r)
            for h in set(r["hazards_named"]):
                self.hazard_idx[h].append(r)
            if r["product"]:
                key = r["product"].lower()
                self.product_idx[key].append(r)
                self.product_names.setdefault(key, r["product"])
            low = r["text"].lower()
            for slug, _name, rx in TOPICS:
                if re.search(rx, low):
                    self.topic_idx[slug].append(r)

        self.topic_names = {s: nm for s, nm, _ in TOPICS}
        # decide which pages exist
        self.origins = {o: v for o, v in self.origin_idx.items() if len(v) >= MIN_ORIGIN}
        self.origin_slug = {o: slugify(o) for o in self.origins}
        self.cats = dict(self.cat_idx)
        self.cat_slug = {c: slugify(c) for c in self.cats}
        self.hazards = {h: v for h, v in self.hazard_idx.items() if len(v) >= MIN_ORIGIN}
        self.hazard_slug = {h: slugify(h) for h in self.hazards}
        self.combos = {k: v for k, v in self.combo_idx.items()
                       if len(v) >= MIN_COMBO and k[0] in self.origins}
        self.topics = {s: v for s, v in self.topic_idx.items() if len(v) >= MIN_TOPIC}
        self.products = {}
        for key, v in self.product_idx.items():
            slug = slugify(self.product_names[key])
            if len(v) >= MIN_PRODUCT and slug and slug not in self.topic_names:
                self.products[slug] = (self.product_names[key], v)

    # --- URLs
    def u_origin(self, o):
        return f"/origin/{self.origin_slug[o]}/"

    def u_cat(self, c):
        return f"/category/{self.cat_slug[c]}/"

    def u_hazard(self, h):
        return f"/hazard/{self.hazard_slug[h]}/"

    def u_combo(self, o, c):
        return f"/origin/{self.origin_slug[o]}/{self.cat_slug[c]}/"

    def u_topic(self, s):
        return f"/product/{s}/"

    def u_product(self, slug):
        return f"/product/{slug}/"

    # --- blocks
    def source_table(self, rs):
        by = defaultdict(list)
        for r in rs:
            by[r["src"]].append(r)
        rows = ""
        for key in ("china", "eu", "korea"):
            if key not in by:
                continue
            ds = sorted(r["date"] for r in by[key])
            rows += (f"<tr><td>{escape(SOURCES[key][0])}</td><td class=\"num\">{n(len(by[key]))}</td>"
                     f"<td>{escape(month_label(ds[0]))} to {escape(month_label(ds[-1]))}</td></tr>")
        return ("<h2>Where the notices come from</h2><div class=\"scroll\"><table>"
                "<tr><th>Source</th><th class=\"num\">Notices</th><th>Period in foodok</th></tr>"
                f"{rows}</table></div>")

    def count_table(self, title, counter, total, head, linker=None, limit=10):
        if not counter:
            return ""
        top = counter.most_common(limit)
        mx = top[0][1]
        rows = ""
        for name, c in top:
            u = linker(name) if linker else None
            label = f'<a href="{escape(u)}">{escape(name)}</a>' if u else escape(name)
            w = max(2, round(100 * c / mx))
            rows += (f"<tr><td>{label}</td><td class=\"num\">{n(c)} ({round(100*c/total)}%)</td>"
                     f"<td class=\"barcell\"><span class=\"bar\" style=\"width:{w}%\"></span></td></tr>")
        return (f"<h2>{escape(title)}</h2><div class=\"scroll\"><table>"
                f"<tr><th>{escape(head)}</th><th class=\"num\">Notices</th><th class=\"barhead\"></th></tr>"
                f"{rows}</table></div>")

    def recent_table(self, rs):
        rows_data = sorted(rs, key=lambda r: r["date"], reverse=True)[:RECENT_ROWS]
        rows = ""
        for r in rows_data:
            hz = ", ".join(r["hazards_named"]) or "Reason not specified"
            rows += (f"<tr><td class=\"date\">{escape(r['date'])}</td>"
                     f"<td>{escape(SOURCES[r['src']][0])}</td>"
                     f"<td>{escape(r['text'])}</td><td>{escape(hz)}</td></tr>")
        return (f"<h2>Latest {len(rows_data)} notices</h2><div class=\"scroll\"><table>"
                "<tr><th>Date</th><th>Source</th><th>Notice</th><th>Reason</th></tr>"
                f"{rows}</table></div>")

    def facts(self, rs):
        by = Counter(r["src"] for r in rs)
        parts = []
        if by.get("china"):
            parts.append(f"{n(by['china'])} from China customs")
        if by.get("eu"):
            parts.append(f"{n(by['eu'])} from the EU RASFF system")
        if by.get("korea"):
            parts.append(f"{n(by['korea'])} from South Korea MFDS")
        s = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
        hz = Counter(h for r in rs for h in r["hazards_named"])
        top = ""
        if hz:
            h, c = hz.most_common(1)[0]
            top = (f" The most common reason is {h.lower()}, named in {n(c)} notices "
                   f"({round(100*c/len(rs))}%).")
        return s, top

    def hazard_links(self, rs, k=6):
        hz = Counter(h for r in rs for h in r["hazards_named"] if h in self.hazards)
        return [(f"{h}", self.u_hazard(h)) for h, _ in hz.most_common(k)]

    def origin_links(self, rs, k=10, exclude=None):
        oc = Counter(o for r in rs for o in set(r["origins"]) if o in self.origins and o != exclude)
        return [(o, self.u_origin(o)) for o, _ in oc.most_common(k)]

    def finish(self, title, desc, path, crumbs, h1, intro, rs, sections):
        s, top = self.facts(rs)
        body = (f"<h1>{escape(h1)}</h1>"
                f"<p class=\"lede\">{intro.format(n=n(len(rs)), s=s, top=top)}</p>"
                f"{self.source_table(rs)}{sections}{self.recent_table(rs)}"
                f"<p class=\"note\">Built {self.today}. Counts reflect only the notices foodok holds "
                f"and the periods shown above, so totals from different sources are not directly comparable.</p>")
        write(path.strip("/") + "/index.html", page(title, desc, path, crumbs, body))

    # --- page builders
    def build_origin(self, o, rs):
        path = self.u_origin(o)
        cats = Counter(r["cat"] for r in rs)
        prods = Counter(r["product"] for r in rs if r["product"])
        prod_link = {self.product_names[k]: slugify(self.product_names[k]) for k in self.product_idx}
        sections = self.count_table(
            f"Food types flagged for {o}", cats, len(rs), "Food category",
            linker=lambda c: self.u_combo(o, c) if (o, c) in self.combos else self.u_cat(c))
        sections += self.count_table(
            "Why shipments are flagged",
            Counter(h for r in rs for h in r["hazards_named"]), len(rs), "Reason",
            linker=lambda h: self.u_hazard(h) if h in self.hazards else None)
        sections += self.count_table(
            "Products named most often (China and Korea notices)", prods, sum(prods.values()) or 1, "Product",
            linker=lambda p: self.u_product(prod_link[p]) if prod_link.get(p) in self.products else None, limit=8)
        title = f"{o} food exports: border rejections and alerts | foodok"
        s, _ = self.facts(rs)
        desc = (f"{n(len(rs))} public food safety notices for {o}-origin products from China customs, "
                f"the EU and South Korea, by food type and reason.")
        intro = (f"foodok holds {{n}} public notices about {escape(o)}-origin food products: {{s}}."
                 "{top}")
        self.finish(title, desc, path, [("foodok", "/"), ("Explore", "/explore/"), (o, None)],
                    f"{o}: food safety rejections and alerts", intro, rs, sections)

    def build_category(self, c, rs):
        path = self.u_cat(c)
        sections = self.count_table(
            "Origin countries with the most notices", Counter(o for r in rs for o in set(r["origins"])),
            len(rs), "Origin",
            linker=lambda o: self.u_combo(o, c) if (o, c) in self.combos else
            (self.u_origin(o) if o in self.origins else None), limit=12)
        sections += self.count_table(
            "Why shipments are flagged",
            Counter(h for r in rs for h in r["hazards_named"]), len(rs), "Reason",
            linker=lambda h: self.u_hazard(h) if h in self.hazards else None)
        title = f"{c}: border rejections and food safety alerts | foodok"
        desc = (f"{n(len(rs))} public notices on {c.lower()} from China customs, the EU and South Korea: "
                "top origins, reasons and the latest cases.")
        intro = (f"foodok holds {{n}} public notices in the category {escape(c.lower())}: {{s}}.{{top}}")
        self.finish(title, desc, path, [("foodok", "/"), ("Explore", "/explore/"), (c, None)],
                    f"{c}: food safety rejections and alerts", intro, rs, sections)

    def build_hazard(self, h, rs):
        path = self.u_hazard(h)
        sections = self.count_table(
            "Origin countries with the most notices", Counter(o for r in rs for o in set(r["origins"])),
            len(rs), "Origin", linker=lambda o: self.u_origin(o) if o in self.origins else None, limit=12)
        sections += self.count_table(
            "Food types affected", Counter(r["cat"] for r in rs), len(rs), "Food category",
            linker=lambda c: self.u_cat(c))
        title = f"{h}: why food shipments get rejected | foodok"
        desc = (f"{n(len(rs))} notices from China, the EU and South Korea where the reason was "
                f"{h.lower()}: origins, food types and recent cases.")
        intro = (f"foodok holds {{n}} public notices where the stated reason was {escape(h.lower())}: {{s}}.")
        self.finish(title, desc, path, [("foodok", "/"), ("Explore", "/explore/"), (h, None)],
                    f"{h}: border rejections and alerts", intro, rs, sections)

    def build_combo(self, o, c, rs):
        path = self.u_combo(o, c)
        sections = self.count_table(
            "Why shipments are flagged",
            Counter(h for r in rs for h in r["hazards_named"]), len(rs), "Reason",
            linker=lambda h: self.u_hazard(h) if h in self.hazards else None)
        prods = Counter(r["product"] for r in rs if r["product"])
        sections += self.count_table("Products named most often", prods, sum(prods.values()) or 1,
                                     "Product", limit=8)
        rel = [(f"All {o} notices", self.u_origin(o)), (f"All {c.lower()} notices", self.u_cat(c))]
        sections += "<h2>Related pages</h2>" + link_list(rel)
        title = f"{o} {c.lower()}: rejections and alerts | foodok"
        desc = (f"{n(len(rs))} public notices on {o}-origin {c.lower()} from China customs, the EU and "
                "South Korea, with reasons and recent cases.")
        intro = (f"foodok holds {{n}} public notices on {escape(c.lower())} from {escape(o)}: {{s}}.{{top}}")
        self.finish(title, desc, path,
                    [("foodok", "/"), ("Explore", "/explore/"), (o, self.u_origin(o)), (c, None)],
                    f"{o} {c.lower()}: rejections and alerts", intro, rs, sections)

    def build_product(self, path, name, rs, kind_note=""):
        sections = self.count_table(
            "Origin countries with the most notices", Counter(o for r in rs for o in set(r["origins"])),
            len(rs), "Origin", linker=lambda o: self.u_origin(o) if o in self.origins else None, limit=12)
        sections += self.count_table(
            "Why shipments are flagged",
            Counter(h for r in rs for h in r["hazards_named"]), len(rs), "Reason",
            linker=lambda h: self.u_hazard(h) if h in self.hazards else None)
        title = f"{name}: border rejections and food safety alerts | foodok"
        desc = (f"{n(len(rs))} public notices on {name.lower()} from China customs, the EU and South Korea: "
                "which origins, which reasons, and the latest cases.")
        intro = (f"foodok holds {{n}} public notices that mention {escape(name.lower())}: {{s}}.{{top}}")
        self.finish(title, desc, path, [("foodok", "/"), ("Explore", "/explore/"), (name, None)],
                    f"{name}: food safety rejections and alerts", intro, rs, sections)

    def build_explore(self):
        def top_items(d, url, k=None, key=lambda kv: -len(kv[1])):
            items = sorted(d.items(), key=key)
            return [(f"{name} ({n(len(v))})", url(name)) for name, v in items[:k]]

        body = ["<h1>Explore food safety notices</h1>",
                "<p class=\"lede\">Browse public rejection and alert notices from China customs, the EU "
                "RASFF system and South Korea MFDS by origin country, food type, reason and product.</p>"]
        body.append("<h2>Origin countries</h2>" + link_list(
            top_items(self.origins, self.u_origin)))
        body.append("<h2>Food categories</h2>" + link_list(
            top_items(self.cats, self.u_cat)))
        body.append("<h2>Reasons</h2>" + link_list(
            top_items(self.hazards, self.u_hazard)))
        topics = [(f"{self.topic_names[s]} ({n(len(v))})", self.u_topic(s))
                  for s, v in sorted(self.topics.items(), key=lambda kv: -len(kv[1]))]
        body.append("<h2>Products</h2>" + link_list(topics))
        prods = [(f"{nm} ({n(len(v))})", self.u_product(sl))
                 for sl, (nm, v) in sorted(self.products.items(), key=lambda kv: -len(kv[1][1]))]
        body.append("<h2>More products named in China and Korea notices</h2>" + link_list(prods))
        combos = [(f"{o}: {c.lower()} ({n(len(v))})", self.u_combo(o, c))
                  for (o, c), v in sorted(self.combos.items(), key=lambda kv: -len(kv[1]))]
        body.append("<h2>Origin and food type</h2>" + link_list(combos))
        write("explore/index.html", page(
            "Explore food safety rejections by country, food type and reason | foodok",
            "Browse public food rejection and alert notices from China, the EU and South Korea by origin, "
            "food type, reason and product.", "/explore/",
            [("foodok", "/"), ("Explore", None)], "\n".join(body)))

    def build_all(self):
        write("seo.css", CSS.strip() + "\n")
        urls = ["/explore/"]
        for o, rs in self.origins.items():
            self.build_origin(o, rs)
            urls.append(self.u_origin(o))
        for c, rs in self.cats.items():
            self.build_category(c, rs)
            urls.append(self.u_cat(c))
        for h, rs in self.hazards.items():
            self.build_hazard(h, rs)
            urls.append(self.u_hazard(h))
        for (o, c), rs in self.combos.items():
            self.build_combo(o, c, rs)
            urls.append(self.u_combo(o, c))
        for s, rs in self.topics.items():
            self.build_product(self.u_topic(s), self.topic_names[s], rs)
            urls.append(self.u_topic(s))
        for slug, (name, rs) in self.products.items():
            self.build_product(self.u_product(slug), name, rs)
            urls.append(self.u_product(slug))
        self.build_explore()
        sm = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for u in urls:
            sm.append(f"<url><loc>{SITE}{u}</loc><lastmod>{self.today}</lastmod></url>")
        sm.append("</urlset>")
        write("sitemap-pages.xml", "\n".join(sm) + "\n")
        return urls


def main():
    recs = build_records()
    site = Site(recs)
    urls = site.build_all()
    print(f"records: {len(recs)}  pages: {len(urls)}")


if __name__ == "__main__":
    main()
