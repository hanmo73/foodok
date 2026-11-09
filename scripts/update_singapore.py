import re, json, html, urllib.request, os
from email.utils import parsedate_to_datetime

URL = 'https://www.sfa.gov.sg/rss/annual-listing-food-alerts'
OUT = 'singapore.json'

req = urllib.request.Request(URL, headers={
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'})
with urllib.request.urlopen(req, timeout=40) as r:
    t = r.read().decode('utf-8', 'ignore')

def clean(x):
    x = re.sub(r'<!\[CDATA\[|\]\]>', '', x)
    return html.unescape(x).strip()

new = []
for it in re.findall(r'<item>(.*?)</item>', t, re.S):
    ti = re.search(r'<title>(.*?)</title>', it, re.S)
    da = re.search(r'<pubDate>(.*?)</pubDate>', it, re.S)
    li = re.search(r'<link>(.*?)</link>', it, re.S)
    if not (ti and da):
        continue
    try:
        d = parsedate_to_datetime(da.group(1).strip()).strftime('%Y-%m-%d')
    except Exception:
        continue
    new.append({'d': d, 's': clean(ti.group(1)), 'f': 'Food alerts',
                'o': 'Singapore', 'n': 'Singapore Food Agency',
                'g': [], 'h': [], 'ko': '', 'kr': '', 'mf': '',
                'u': clean(li.group(1)) if li else ''})

old = []
if os.path.exists(OUT):
    old = json.load(open(OUT, encoding='utf-8'))
seen = {x['u'] for x in new}
merged = new + [x for x in old if x.get('u') not in seen]
merged.sort(key=lambda x: x['d'], reverse=True)
json.dump(merged, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('singapore items', len(merged))
