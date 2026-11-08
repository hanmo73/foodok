#!/usr/bin/env python3
"""Update korea.json from the MFDS imported-food nonconformity list (impfood.mfds.go.kr).
Usage: python3 scripts/update_korea.py [dry|live]
- Fetches the list pages (limit=100), parses items, merges NEW items into korea.json.
- Existing records are never modified or removed.
- Safety: aborts without writing if parsing looks wrong.
"""
import sys, re, json, html, time, urllib.request, urllib.parse

BASE = "https://impfood.mfds.go.kr/CFCEE01F01"
OUT = "korea.json"
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

COUNTRY = {
 '중국':'China','베트남':'Vietnam','태국':'Thailand','이탈리아':'Italy','인도':'India','일본':'Japan','미국':'United States',
 '인도네시아':'Indonesia','스페인':'Spain','독일':'Germany','필리핀':'Philippines','미얀마':'Myanmar','호주':'Australia',
 '프랑스':'France','스리랑카':'Sri Lanka','페루':'Peru','러시아':'Russia','터키':'Turkey','튀르키예':'Turkey','캐나다':'Canada',
 '캄보디아':'Cambodia','이집트':'Egypt','대만':'Taiwan','네팔':'Nepal','우즈베키스탄':'Uzbekistan','폴란드':'Poland',
 '방글라데시':'Bangladesh','싱가포르':'Singapore','영국':'United Kingdom','말레이시아':'Malaysia','뉴질랜드':'New Zealand',
 '브루나이':'Brunei','우크라이나':'Ukraine','네덜란드':'Netherlands','브라질':'Brazil','키르기스스탄':'Kyrgyzstan',
 '체코':'Czechia','리비아':'Libya','몽골':'Mongolia','불가리아':'Bulgaria','세이셸':'Seychelles','파키스탄':'Pakistan',
 '홍콩':'Hong Kong','멕시코':'Mexico','칠레':'Chile','아르헨티나':'Argentina','에콰도르':'Ecuador','콜롬비아':'Colombia',
 '벨기에':'Belgium','오스트리아':'Austria','스위스':'Switzerland','포르투갈':'Portugal','그리스':'Greece','헝가리':'Hungary',
 '루마니아':'Romania','덴마크':'Denmark','노르웨이':'Norway','스웨덴':'Sweden','핀란드':'Finland','아일랜드':'Ireland',
 '이스라엘':'Israel','이란':'Iran','사우디아라비아':'Saudi Arabia','아랍에미리트':'United Arab Emirates','남아프리카공화국':'South Africa',
 '모로코':'Morocco','케냐':'Kenya','에티오피아':'Ethiopia','나이지리아':'Nigeria','가나':'Ghana','튀니지':'Tunisia','라오스':'Laos',
 '카자흐스탄':'Kazakhstan','조지아':'Georgia','아르메니아':'Armenia','아제르바이잔':'Azerbaijan','크로아티아':'Croatia',
 '세르비아':'Serbia','슬로바키아':'Slovakia','슬로베니아':'Slovenia','리투아니아':'Lithuania','라트비아':'Latvia',
 '에스토니아':'Estonia','벨라루스':'Belarus','몰도바':'Moldova','북마케도니아':'North Macedonia','아이슬란드':'Iceland',
 '쿠바':'Cuba','파나마':'Panama','코스타리카':'Costa Rica','과테말라':'Guatemala','도미니카공화국':'Dominican Republic',
 '온두라스':'Honduras','니카라과':'Nicaragua','볼리비아':'Bolivia','우루과이':'Uruguay','파라과이':'Paraguay','베네수엘라':'Venezuela',
 '피지':'Fiji','파푸아뉴기니':'Papua New Guinea','한국':'South Korea','대한민국':'South Korea','몰디브':'Maldives','부탄':'Bhutan',
 '레바논':'Lebanon','요르단':'Jordan','쿠웨이트':'Kuwait','카타르':'Qatar','오만':'Oman','이라크':'Iraq','탄자니아':'Tanzania',
 '우간다':'Uganda','모잠비크':'Mozambique','마다가스카르':'Madagascar','마카오':'Macau','투르크메니스탄':'Turkmenistan',
 '타지키스탄':'Tajikistan','아프가니스탄':'Afghanistan','북한':'North Korea','몬테네그로':'Montenegro','보스니아헤르체고비나':'Bosnia and Herzegovina',
 '알바니아':'Albania','키프로스':'Cyprus','몰타':'Malta','룩셈부르크':'Luxembourg','세네갈':'Senegal','코트디부아르':'Ivory Coast',
 '카메룬':'Cameroon','잠비아':'Zambia','짐바브웨':'Zimbabwe','수단':'Sudan','알제리':'Algeria','엘살바도르':'El Salvador',
 '자메이카':'Jamaica','트리니다드토바고':'Trinidad and Tobago','가이아나':'Guyana','수리남':'Suriname','솔로몬제도':'Solomon Islands',
 '사모아':'Samoa','통가':'Tonga','바누아투':'Vanuatu','동티모르':'Timor-Leste','마셜제도':'Marshall Islands','괌':'Guam',
}
OFFICE_BASE = {'서울':'Seoul Office','경인':'Gyeongin Office','부산':'Busan Office','광주':'Gwangju Office','대전':'Daejeon Office','대구':'Daegu Office'}
OFFICE_SUB = {
 '미추홀':'Michuhol','평택':'Pyeongtaek','광주':'Gwangju','용인':'Yongin','신항':'New Port','감천':'Gamcheon Port','감천항':'Gamcheon Port',
 '신선대':'Sinseondae','양산':'Yangsan','북항':'North Port','천안':'Cheonan','인천항':'Incheon Port','인천':'Incheon Port','항만':'Incheon Port',
}
UNKNOWN = set()

# (regex, group, hazard)
RULES = [
 (r'농약|잔류허용기준', 'Pesticide residues', 'Pesticide residue over limit'),
 (r'용출|일차방향족아민|형광증백제|과망간산칼륨|증발잔류물|침출', 'Chemical contaminants', 'Migration from food contact material over limit'),
 (r'대장균', 'Bacteria and mold', 'E. coli / coliforms over limit'),
 (r'세균수|일반세균', 'Bacteria and mold', 'Bacterial count over limit'),
 (r'리스테리아', 'Bacteria and mold', 'Listeria monocytogenes detected'),
 (r'살모넬라', 'Bacteria and mold', 'Salmonella detected'),
 (r'비브리오|세균발육|곰팡이|진균|황색포도|장염|바실러스|클로스트리디|캠필로', 'Bacteria and mold', 'Microbiological test failed'),
 (r'유산균수|효모수', 'Bacteria and mold', 'Microbiological test failed'),
 (r'타르색소|식용색소', 'Additives and colours', 'Unauthorized synthetic (tar) dye'),
 (r'사이클라메이트', 'Additives and colours', 'Cyclamate (sweetener) not permitted'),
 (r'이산화황', 'Additives and colours', 'Sulfur dioxide over limit'),
 (r'보존료|소브산|안식향산|데히드로초산|프로피온산|파라옥시', 'Additives and colours', 'Preservative not permitted or over limit'),
 (r'사용기준', 'Additives and colours', 'Additive used outside permitted standard'),
 (r'금속성\s*이물|금속이물|쇳가루', 'Foreign bodies', 'Metallic foreign matter'),
 (r'산가|과산화물가', 'Spoilage and quality', 'Acid value over limit (rancidity)'),
 (r'관능', 'Spoilage and quality', 'Failed sensory inspection'),
 (r'벤조피렌|벤조\(a\)피렌', 'Chemical contaminants', 'Benzo[a]pyrene over limit'),
 (r'아플라톡신|오크라톡신|제랄레논|푸모니신|데옥시니발레놀', 'Mycotoxins', 'Mycotoxin (aflatoxin / ochratoxin) over limit'),
 (r'GM|유전자', 'GMO', 'Unauthorized GMO detected'),
 (r'방사선', 'Other', 'Irradiation not permitted'),
 (r'히스타민', 'Other', 'Histamine over limit'),
 (r'복어독', 'Natural toxins', 'Natural toxin (pufferfish) over limit'),
 (r'아세톤|헥산|용매', 'Chemical contaminants', 'Solvent residue over limit'),
 (r'메탄올', 'Chemical contaminants', 'Methanol over limit'),
 (r'붕해', 'Other', 'Disintegration test failed'),
 (r'니트로푸란|메트로니다졸|말라카이트|클로람페니콜|엔로플록사신|동물용의약품|항생물질|AOZ|류코', 'Veterinary drug residues', 'Veterinary drug residue'),
 (r'납|카드뮴|수은|비소|안티몬|중금속', 'Heavy metals', 'Heavy metal over limit'),
]
PRODUCE = ('Fruit and vegetables','Herbs and spices','Cereals, bakery and sweets','Nuts and seeds','Coffee, tea and cocoa')
ANIMAL = ('Fish and seafood','Meat and poultry','Milk and eggs')
MIG = ('Chemical contaminants', 'Migration from food contact material over limit')

def classify(kr, food_cat=''):
    gs, hs = [], []
    for rx, g, h in RULES:
        if h == 'Heavy metal over limit' and '표시량' in kr:
            continue
        if h == 'Additive used outside permitted standard' and ('Preservative not permitted or over limit' in hs or 'Unauthorized synthetic (tar) dye' in hs):
            continue
        if re.search(rx, kr):
            if h not in hs: hs.append(h)
            if g not in gs: gs.append(g)
    if food_cat == 'Food contact materials':
        if MIG[1] not in hs and 'Heavy metal over limit' not in hs:
            hs.append(MIG[1])
            if MIG[0] not in gs:
                gs.append(MIG[0])
    if not hs:
        if food_cat in ANIMAL and re.search(r'mg/kg|검출', kr):
            hs, gs = ['Veterinary drug residue'], ['Veterinary drug residues']
        elif food_cat in PRODUCE + ANIMAL and re.search(r'기준|규격', kr) and not re.search(r'%|표시량', kr):
            hs, gs = ['Pesticide residue over limit'], ['Pesticide residues']
        elif re.search(r'규격|기준|함량|성분|%|표시량|산도|수분|검출', kr):
            hs, gs = ['Content or composition does not meet standard'], ['Composition and nutrients']
        else:
            hs, gs = ['Other (see Korean notice)'], ['Other']
    return gs[:3], hs[:3]

FOOD_RULES = [
 ('Alcohol', r'와인|맥주|위스키|소주|막걸리|보드카|리큐르|청주|증류주|주류|키르시|kirsch|wine|beer|whisk|vodka|sake|liquor|brandy|gin\b|rum\b'),
 ('Coffee, tea and cocoa', r'커피|코코아|카카오|녹차|홍차|티백|차류|coffee|\btea\b|cocoa|cacao|matcha'),
 ('Drinks', r'음료|주스|알코올|zero|탄산|드링크|과즙|생수|워터|drink|juice|beverage|water|cola|soda|smoothie'),
 ('Herbs and spices', r'향신|고춧가루|후추|강황|계피|카레|허브|커민|향료|spice|herb|cumin|turmeric|chili powder|chilli powder|pepper powder|seed powder|cinnamon|curry|paprika powder|masala'),
 ('Sauces and prepared food', r'소스|간장|된장|고추장|양념|조미|드레싱|식초|케첩|마요네즈|소금|sauce|seasoning|paste|vinegar|dressing|ketchup|mayonnaise|salt\b|soup|ready|instant'),
 ('Fats and oils', r'기름|유지|식용유|오일|\boil\b|\bfat\b|shortening|margarine'),
 ('Milk and eggs', r'우유|유제품|치즈|요구르트|버터|계란|크림|밀크|milk|cheese|yogurt|yoghurt|egg|cream|creme|gorgonzola|pecorino|mozzarella|parmesan|feta'),
 ('Meat and poultry', r'육포|햄|소시지|베이컨|닭|돼지|소고기|쇠고기|meat|chicken|pork|beef|sausage|ham\b|jerky|bacon'),
 ('Fish and seafood', r'어묵|오징어|새우|멸치|젓갈|해조|미역|다시마|김(?!치)|어패류|참치|고등어|fish|shrimp|squid|seaweed|laver|tuna|oyster|seafood|anchov|crab|sea cucumber'),
 ('Nuts and seeds', r'견과|땅콩|아몬드|호두|캐슈|피스타치오|참깨|들깨|해바라기|\bnut|almond|sesame|peanut|cashew|pistachio|sunflower|chia|walnut'),
 ('Cereals, bakery and sweets', r'과자|피타|칩|tempeh|pita|chip|crispy|pie|pizza|dumpling|만두|쿠키|빵|면류|국수|라면|파스타|밀가루|쌀|떡|시리얼|초콜릿|캔디|젤리|사탕|당류|설탕|엿|비스킷|케이크|곡|전분|두류|콩|biscuit|cookie|bread|noodle|pasta|rice|flour|cereal|chocolate|candy|jelly|sugar|cake|snack|cracker|wafer|oat|bean|cornflake|syrup|honey|jam\b'),
 ('Fruit and vegetables', r'과일|채소|야채|우베|무청|추출분말|ube|radish|yam|leaf|leaves|powder|고추|마늘|양파|김치|절임|장아찌|토마토|망고|두리안|바나나|사과|딸기|포도|오렌지|귤|감자|고구마|배추|버섯|채|과채|fruit|vegetable|mango|durian|banana|apple|chili|chilli|pepper|garlic|onion|kimchi|pickle|tomato|mushroom|lemon|lime|orange|berry|grape|melon|papaya|pineapple|coconut|avocado|jackfruit|lychee|dried'),
]

def food_category(cls, item, ko, en):
    if re.search(r'기구|용기|포장', cls): return 'Food contact materials'
    if '건강기능' in cls: return 'Supplements and fortified foods'
    txt = f"{item} {ko} {en}".lower()
    if '수산' in cls: return 'Fish and seafood'
    if '축산' in cls:
        return 'Milk and eggs' if re.search(r'우유|유가공|치즈|버터|계란|milk|cheese|egg', txt) else 'Meat and poultry'
    for cat, rx in FOOD_RULES:
        if re.search(rx, txt): return cat
    if '농' in cls or '임산' in cls: return 'Fruit and vegetables'
    return 'Other food'

def office_en(ko):
    m = re.match(r'\s*(서울|경인|부산|광주|대전|대구)청?\s*(?:\(([^)]*)\))?', ko)
    if not m:
        UNKNOWN.add('office:' + ko); return ko
    base = OFFICE_BASE[m.group(1)]
    sub = (m.group(2) or '').strip()
    if not sub: return base
    if sub == '공항':
        sub_en = 'Gimpo Airport' if m.group(1) == '서울' else 'Incheon Airport'
    else:
        sub_en = OFFICE_SUB.get(sub)
        if not sub_en:
            UNKNOWN.add('office:' + ko); sub_en = sub
    return f"{base} ({sub_en})"

def country_en(ko):
    ko = ko.strip()
    if ko in COUNTRY: return COUNTRY[ko]
    if ko and not re.search(r'[가-힣]', ko): return ko
    UNKNOWN.add('country:' + ko); return ko

def title_en(en, ko):
    en = re.sub(r'\s+', ' ', en or '').strip()
    if not en or re.search(r'[가-힣]', en): return ko
    def fix(m):
        t = m.group(0)
        return t if re.search(r'\d', t) else t.capitalize()
    return re.sub(r"[A-Za-z0-9']+", fix, en)

def clean(t):
    return html.unescape(re.sub(r'<[^>]+>', '', t or '')).replace('\ufeff', '').strip()

def field(chunk, label):
    m = re.search(r'<strong>\s*' + re.escape(label) + r'\s*</strong>\s*<span[^>]*>(.*?)</span>', chunk, re.S)
    return clean(m.group(1)) if m else ''

def parse_page(t):
    starts = [m.start() for m in re.finditer(r'<strong title="제품한글명">', t)]
    items = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(t)
        c = t[s:e]
        m = re.search(r'<strong title="제품한글명">(.*?)</strong>', c, re.S)
        ko = clean(m.group(1)) if m else ''
        m = re.search(r'<span title="제품영문명">(.*?)</span>', c, re.S)
        en = clean(m.group(1)) if m else ''
        cls = field(c, '제품구분'); item = field(c, '품목명'); ctry = field(c, '제조국가')
        mf = field(c, '제조/수출회사'); kr = field(c, '위반내역(시험항목/기준/결과)')
        office = field(c, '처리기관'); d = field(c, '부적합일자')
        dm = re.search(r'(20\d\d-\d\d-\d\d)', d)
        if not dm:
            dm = re.search(r'부적합일자.*?(20\d\d-\d\d-\d\d)', c, re.S)
        d = dm.group(1) if dm else ''
        items.append(dict(ko=ko, en=en, cls=cls, item=item, ctry=ctry, mf=mf, kr=kr, office=office, d=d))
    return items

def fetch(page, limit=100):
    url = BASE + '?' + urllib.parse.urlencode({'page': page, 'limit': limit})
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode('utf-8', 'ignore')
        except Exception as ex:
            print('fetch error', page, attempt, ex)
            time.sleep(5)
    return ''

def key(d, ko, mf, kr):
    return re.sub(r'\s+|\ufeff', '', f"{d}|{ko}|{mf}|{kr}")

def to_record(it):
    f = food_category(it['cls'], it['item'], it['ko'], it['en'])
    g, h = classify(it['kr'], f)
    o = country_en(it['ctry'])
    name = title_en(it['en'], it['ko'])
    s = f"{name} from {o}: {h[0]}" + (f" (+{len(h)-1} more)" if len(h) > 1 else "")
    return {"d": it['d'], "s": s, "f": f, "o": o, "n": office_en(it['office']), "g": g, "h": h,
            "ko": it['ko'], "kr": it['kr'], "mf": it['mf']}

def main():
    items = []
    for p in range(1, 11):
        t = fetch(p)
        got = parse_page(t)
        print(f"page {p}: {len(got)} items")
        if not got: break
        if items and got[0] == items[0]:
            break
        items += got
        if len(got) < 100: break
        time.sleep(1)
    bad = [i for i in items if not i['d'] or not i['ko'] or not i['kr']]
    print(f"parsed {len(items)} items, incomplete {len(bad)}")
    if len(items) < 50 or len(bad) > max(3, len(items) * 0.03):
        print("ABORT: parsing looks wrong, nothing written"); sys.exit(1)
    try:
        existing = json.load(open(OUT, encoding='utf-8'))
    except Exception as ex:
        print("ABORT: cannot read existing", OUT, ex); sys.exit(1)
    if not isinstance(existing, list) or len(existing) < 100:
        print("ABORT: existing file looks wrong"); sys.exit(1)
    seen = {key(x['d'], x['ko'], x['mf'], x['kr']) for x in existing}
    new, matched = [], 0
    for it in items:
        if not (it['d'] and it['ko'] and it['kr']): continue
        k = key(it['d'], it['ko'], it['mf'], it['kr'])
        if k in seen:
            matched += 1; continue
        seen.add(k); new.append(to_record(it))
    print(f"already in file: {matched}, new: {len(new)}")
    if UNKNOWN: print("unmapped:", sorted(UNKNOWN))
    for r in new[:3]: print(json.dumps(r, ensure_ascii=False)[:400])
    if len(new) > 150:
        print("ABORT: too many new items at once, check manually"); sys.exit(1)
    if MODE != 'live':
        print("DRY RUN: nothing written"); return
    if not new:
        print("no changes"); return
    out = new + existing
    out.sort(key=lambda x: x['d'], reverse=True)
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print("written", len(out))

if __name__ == '__main__':
    main()
