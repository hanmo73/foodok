import json
import urllib.request

URL = "https://recalls-rappels.canada.ca/sites/default/files/opendata-donneesouvertes/HCRSAMOpenData.json"
OUT = "canada.json"


def clean(value):
    if not isinstance(value, str):
        return ""
    return value.replace("\u200b", "").strip()


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "foodok.org"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8-sig"))

    rows = []
    for it in data:
        if clean(it.get("Organization")) != "CFIA":
            continue
        recall_class = clean(it.get("Recall class"))
        rtype = "Food Recall"
        if recall_class:
            rtype = "Food Recall (" + recall_class + ")"
        rows.append({
            "id": clean(it.get("NID")),
            "date": clean(it.get("Last updated"))[:10],
            "type": rtype,
            "title": clean(it.get("Title")),
            "product": clean(it.get("Product")),
            "reason": clean(it.get("Issue")),
            "url": clean(it.get("URL")),
            "country": "Canada",
            "source": "Canada CFIA",
        })

    if not rows:
        raise SystemExit("No items returned; keeping existing file")

    rows.sort(key=lambda r: r["date"], reverse=True)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"Saved {len(rows)} alerts")


if __name__ == "__main__":
    main()
