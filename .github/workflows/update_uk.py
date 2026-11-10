import json
import urllib.request

URL = "https://data.food.gov.uk/food-alerts/id?_limit=1000&_sort=-created"
OUT = "uk.json"

TYPE_LABELS = {
    "AA": "Allergy Alert",
    "PRIN": "Product Recall",
    "FAFA": "Food Alert for Action",
}


def first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def text_of(value):
    value = first(value)
    if isinstance(value, dict):
        return value.get("label") or value.get("@id") or ""
    return value or ""


def main():
    req = urllib.request.Request(URL, headers={"Accept": "application/json", "User-Agent": "foodok.org"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)

    rows = []
    for it in data.get("items", []):
        raw_type = text_of(it.get("alertType"))
        code = raw_type.rstrip("/").split("/")[-1] if raw_type else ""

        products = it.get("productDetails") or []
        if not isinstance(products, list):
            products = [products]
        product_names = [p.get("productName", "") for p in products if isinstance(p, dict)]

        problems = it.get("problem") or []
        if not isinstance(problems, list):
            problems = [problems]
        reasons = []
        for p in problems:
            if isinstance(p, dict):
                reasons.append(p.get("riskStatement") or p.get("pathogenRiskStatement") or "")
        reasons = [r for r in reasons if r]

        rows.append({
            "id": it.get("notation") or it.get("@id"),
            "date": (it.get("created") or "")[:10],
            "type": TYPE_LABELS.get(code, code),
            "title": it.get("title") or it.get("shortTitle") or "",
            "product": "; ".join(n for n in product_names if n),
            "reason": "; ".join(reasons),
            "url": it.get("alertURL") or it.get("@id") or "",
            "country": "United Kingdom",
            "source": "UK FSA",
        })

    if not rows:
        raise SystemExit("No items returned; keeping existing file")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(rows)} alerts")


if __name__ == "__main__":
    main()
