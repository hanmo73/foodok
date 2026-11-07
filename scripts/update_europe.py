#!/usr/bin/env python3
"""
foodok.org - rebuild europe.json from the public EU RASFF Window list.

Usage (from the repo root):
  python3 scripts/update_europe.py dry     -> writes data/europe_candidate.json and data/europe_report.json
  python3 scripts/update_europe.py live    -> writes europe.json (what the site reads)
  python3 scripts/update_europe.py dry path/to/rasff_list.json   -> test with a saved list (no network)

europe.json is only written when the run looks healthy (enough rows, no fetch errors).
"""
import json, os, sys, time, collections, urllib.request
from datetime import datetime, timedelta, timezone

MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
SRC = sys.argv[2] if len(sys.argv) > 2 else None
MIN_ROWS = 4000
WINDOW_DAYS = 365
URL = "https://webgate.ec.europa.eu/rasff-window/backend/public/notification/search/consolidated/"
HDR = {"Content-Type": "application/json", "Accept": "application/json",
       "User-Agent": "FoodOK/1.0 (+https://foodok.org)"}

CAT_MAP = {
    "fruits and vegetables": "Fruit and vegetables",
    "poultry meat and poultry meat products": "Meat and poultry",
    "meat and meat products (other than poultry)": "Meat and poultry",
    "animal by-products": "Meat and poultry",
    "nuts, nut products and seeds": "Nuts and seeds",
    "dietetic foods, food supplements and fortified foods": "Supplements and fortified foods",
    "cereals and bakery products": "Cereals, bakery and sweets",
    "confectionery": "Cereals, bakery and sweets",
    "ices and desserts": "Cereals, bakery and sweets",
    "fish and fish products": "Fish and seafood",
    "bivalve molluscs and products thereof": "Fish and seafood",
    "crustaceans and products thereof": "Fish and seafood",
    "cephalopods and products thereof": "Fish and seafood",
    "gastropods": "Fish and seafood",
    "herbs and spices": "Herbs and spices",
    "other food product / mixed": "Other food",
    "food additives and flavourings": "Other food",
    "live animals": "Other food",
    "feed materials": "Feed and pet food",
    "pet food": "Feed and pet food",
    "compound feeds": "Feed and pet food",
    "feed additives": "Feed and pet food",
    "feed premixtures": "Feed and pet food",
    "milk and milk products": "Milk and eggs",
    "eggs and egg products": "Milk and eggs",
    "cocoa and cocoa preparations, coffee and tea": "Coffee, tea and cocoa",
    "food contact materials": "Food contact materials",
    "prepared dishes and snacks": "Sauces and prepared food",
    "soups, broths, sauces and condiments": "Sauces and prepared food",
    "fats and oils": "Fats and oils",
    "non-alcoholic beverages": "Drinks",
    "natural mineral waters": "Drinks",
    "water for human consumption (other)": "Drinks",
    "alcoholic beverages": "Alcohol",
    "wine": "Alcohol",
    "honey and royal jelly": "Honey",
}


def iso(s):
    s = str(s or "")
    return s[6:10] + "-" + s[3:5] + "-" + s[0:2] if len(s) >= 10 else ""


def post(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=HDR, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def fetch_rows(cutoff):
    rows = []
    for p in range(1, 120):
        d = None
        for attempt in range(4):
            try:
                d = post({"parameters": {"pageNumber": p, "itemsPerPage": 100}})
                break
            except Exception as e:
                last = e
                time.sleep(3)
        if d is None:
            raise RuntimeError("page %d failed: %r" % (p, last))
        lst = d.get("notifications") or []
        if not lst:
            break
        page_dates = []
        for n in lst:
            dd = iso(n.get("ecValidationDate"))
            page_dates.append(dd)
            rows.append({
                "d": dd,
                "s": n.get("subject"),
                "cat": (n.get("productCategory") or {}).get("description"),
                "cls": (n.get("notificationClassification") or {}).get("description"),
                "risk": (n.get("riskDecision") or {}).get("description"),
                "n": (n.get("notifyingCountry") or {}).get("organizationName"),
                "o": [x.get("organizationName") for x in (n.get("originCountries") or [])],
            })
        known = [x for x in page_dates if x]
        if known and max(known) < cutoff:
            break
        time.sleep(0.3)
    return rows


def load_training():
    with open("data/europe_training.json", encoding="utf-8") as f:
        return json.load(f)


def build_classifier(train):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.pipeline import make_union
    from sklearn.preprocessing import MultiLabelBinarizer
    texts = [s + " || " + (c or "") for s, c, g in train]
    mlb = MultiLabelBinarizer()
    Y = mlb.fit_transform([g for s, c, g in train])
    vec = make_union(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=60000),
    )
    X = vec.fit_transform(texts)
    clf = OneVsRestClassifier(LogisticRegression(max_iter=2000, C=10)).fit(X, Y)

    def predict(items):
        if not items:
            return []
        pr = clf.predict_proba(vec.transform([s + " || " + (c or "") for s, c in items]))
        out = []
        for row in pr:
            labels = [mlb.classes_[i] for i, v in enumerate(row) if v >= 0.4]
            if not labels:
                labels = [mlb.classes_[int(row.argmax())]]
            out.append(labels)
        return out
    return predict


def main():
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    if SRC:
        with open(SRC, encoding="utf-8") as f:
            rows = json.load(f)["rows"]
            rows = [{"d": r["d"], "s": r["s"], "cat": r["cat"], "cls": r["cls"], "risk": r["risk"],
                     "n": r["n"], "o": r["o"]} for r in rows]
    else:
        rows = fetch_rows(cutoff)
    rows = [r for r in rows if r["d"] and r["d"] >= cutoff and (r["s"] or "").strip()]
    if len(rows) < MIN_ROWS:
        print("ABORT: only %d rows (need %d). europe.json left unchanged." % (len(rows), MIN_ROWS))
        sys.exit(1)

    train = load_training()
    known = {(s.strip(), c): g for s, c, g in train}
    predict = build_classifier(train)

    unknown_idx = [i for i, r in enumerate(rows) if (r["s"].strip(), r["cat"]) not in known]
    preds = predict([(rows[i]["s"].strip(), rows[i]["cat"]) for i in unknown_idx])
    pred_by_idx = dict(zip(unknown_idx, preds))

    out = []
    unseen_cats = collections.Counter()
    for i, r in enumerate(rows):
        key = (r["s"].strip(), r["cat"])
        g = known.get(key) or pred_by_idx.get(i) or ["Not specified"]
        f = CAT_MAP.get(r["cat"])
        if f is None:
            unseen_cats[r["cat"]] += 1
            f = "Other food"
        out.append({
            "d": r["d"], "s": r["s"].strip(), "f": f,
            "o": [x for x in r["o"] if x], "n": r["n"] or "",
            "r": r["risk"] or "", "cl": r["cls"] or "",
            "g": g, "h": [],
        })
    out.sort(key=lambda x: x["d"], reverse=True)

    report = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": MODE,
        "rows": len(out),
        "date_range": [out[-1]["d"], out[0]["d"]],
        "rows_with_known_labels": len(rows) - len(unknown_idx),
        "rows_with_predicted_labels": len(unknown_idx),
        "unseen_categories": dict(unseen_cats),
        "group_counts": dict(collections.Counter(x for r in out for x in r["g"]).most_common()),
    }
    os.makedirs("data", exist_ok=True)
    if MODE == "live":
        with open("europe.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print("WROTE europe.json with %d rows" % len(out))
    else:
        with open("data/europe_candidate.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print("WROTE data/europe_candidate.json with %d rows" % len(out))
    with open("data/europe_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
