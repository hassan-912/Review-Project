"""Auditable local Arabic/English equivalence checks, without translation APIs.

This is a bounded terminology/translation check, not a general-purpose translator.
Uncovered wording never establishes a confirmed translation error. Raw source
values are retained; normalized meanings and compatibility bases are separate.
Identity names/numbers/dates deliberately do not use phonetic normalization.
"""
from collections import Counter
from difflib import SequenceMatcher
import re
import unicodedata


VERSION='ar-en-equivalence-v1'
FIELDS={'employer_name','occupation','education_name','education_course','employer_address',
        'hotel_name','hotel_address','birth_city','birth_country','nationality','trip_sponsor'}


def normal(text):
    text=unicodedata.normalize('NFKC',str(text or '')).casefold()
    text=re.sub(r'[\u064b-\u065f\u0670\u0640]','',text)
    text=text.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ٱ':'ا','ى':'ي','ة':'ه'}))
    return re.sub(r'[^\w]+',' ',text).strip()


# Terms are shared concepts, not customer-specific phrase replacements.
GROUPS={
    'trade':('trade','trading','تجارة','تجاره'),
    'distribution':('distribution','distributing','توزيع'),
    'pharmaceuticals':('pharmaceuticals','medicines','medications','drugs','ادوية','ادويه'),
    'company':('company','co','شركة','شركه','مؤسسة','مؤسسه'),
    'supervisor':('supervisor','supervision','مشرف','اشراف'),
    'manager':('manager','مدير'),
    'sales':('sales','مبيعات'),
    'accountant':('accountant','محاسب'),
    'doctor':('doctor','physician','طبيب'),
    'engineer':('engineer','مهندس'),
    'teacher':('teacher','مدرس','معلم'),
    'driver':('driver','سائق'),
    'tourism':('tourism','tourist','سياحة','سياحه'),
    'guide':('guide','مرشد'),
    'university':('university','جامعة','جامعه'),
    'faculty':('faculty','college','كلية','كليه'),
    'alexandria':('alexandria','اسكندرية','اسكندريه'),
    'cairo':('cairo','قاهرة','قاهره'),
    'giza':('giza','جيزة','جيزه'),
    'sohag':('sohag','suhag','سوهاج'),
    'bachelor':('bachelor','bachelors','بكالوريوس','ليسانس'),
    'masters':('master','masters','ماجستير'),
    'doctorate':('doctorate','phd','دكتوراه'),
    'physical_education':('physical education','sports education','تربية رياضية','تربيه رياضيه'),
    'training':('training','coaching','تدريب'),
    'teaching':('teaching','تدريس'),
    'handball':('handball','كرة يد','كره يد','كرة اليد','كره اليد'),
    'football':('football','soccer','كرة قدم','كره قدم','كرة القدم','كره القدم'),
    'accounting':('accounting','محاسبة','محاسبه'),
    'commerce':('commerce','تجاري','تجارية','تجاريه'),
    'engineering':('engineering','هندسة','هندسه'),
    'medicine':('medicine','طب'),
    'law':('law','حقوق','قانون'),
    'computer_science':('computer science','علوم الحاسب','علوم الحاسوب'),
    'egypt':('egy','egypt','egyptian','مصر','مصري'),
    'self':('self','myself','نفسي'),
}
TERMS={normal(term):concept for concept,terms in GROUPS.items() for term in terms}
STOP={'and','of','for','the','in','at','to','by','و','في','من','ل','لل','s'}
LANGUAGES={}
for english,arabic in (
    ('arabic',('عربي','عربية','العربية')),('english',('انجليزي','انجليزية','الانجليزية','انكليزي','انكليزية')),
    ('french',('فرنسي','فرنسية')),('german',('الماني','المانية')),('spanish',('اسباني','اسبانية')),
    ('italian',('ايطالي','ايطالية')),('romanian',('روماني','رومانية')),('russian',('روسي','روسية')),
    ('turkish',('تركي','تركية')),('portuguese',('برتغالي','برتغالية')),('dutch',('هولندي','هولندية')),
    ('greek',('يوناني','يونانية')),('hindi',('هندي','هندية')),('urdu',('اردو',)),
    ('chinese',('صيني','صينية')),('japanese',('ياباني','يابانية')),('korean',('كوري','كورية')),
    ('swedish',('سويدي','سويدية')),('hebrew',('عبري','عبرية')),
):
    for alias in (english,*arabic):LANGUAGES[normal(alias)]=english


def language_set(value):
    text=normal(value)
    text=re.sub(r'\b(?:and|language|languages)\b',' ',text)
    words=[]
    for word in text.split():
        if word in ('و','لغة','لغه','اللغة','اللغه'):continue
        options=(word,word[1:] if word.startswith('و') else word)
        found=next((LANGUAGES[v] for v in options if v in LANGUAGES),None)
        if found is None:return None
        words.append(found)
    return set(words) if words else None


def phonetic(word):
    # Organization-name compatibility only; never for passport personal identity.
    arabic={'ب':'b','ت':'t','ث':'th','ج':'g','ح':'h','خ':'kh','د':'d','ذ':'dh','ر':'r','ز':'z',
            'س':'s','ش':'sh','ص':'s','ض':'d','ط':'t','ظ':'z','ع':'','غ':'gh','ف':'f','ق':'k',
            'ك':'k','ل':'l','م':'m','ن':'n','ه':'h','ا':'','و':'','ي':'','ء':''}
    word=''.join(arabic.get(c,c) for c in normal(word))
    word=re.sub(r'[aeiouy]','',word)
    return re.sub(r'(.)\1+',r'\1',word)


def terms(value):
    words=normal(value).split();concepts=[];unknown=[];variants=[];i=0
    while i<len(words):
        found=None
        for size in range(min(4,len(words)-i),0,-1):
            phrase=' '.join(words[i:i+size])
            if phrase in TERMS:found=(TERMS[phrase],size);break
        if found:
            concepts.append(found[0]);i+=found[1];continue
        word=words[i]
        candidates=[word]
        if word.startswith('و') and len(word)>3:candidates.append(word[1:])
        for token in list(candidates):
            for prefix in ('لل','ال','ل','ب'):
                if token.startswith(prefix) and len(token)>len(prefix)+2:candidates.append(token[len(prefix):])
        direct=next((TERMS[c] for c in candidates if c in TERMS),None)
        if direct:concepts.append(direct)
        elif word not in STOP:
            # A unique one-edit spelling variant of a longer known Arabic term
            # is recorded explicitly; unknown proper names are not spell-fixed.
            near={concept for alias,concept in TERMS.items() if ' ' not in alias and len(alias)>=5 and
                  re.search('[\u0600-\u06ff]',alias) and any(abs(len(c)-len(alias))<=1 and
                  SequenceMatcher(None,c,alias).ratio()>=.88 for c in candidates)}
            if len(near)==1:
                concept=next(iter(near));concepts.append(concept);variants.append(dict(read=word,concept=concept))
            else:unknown.append(word)
        i+=1
    return dict(concepts=sorted(concepts),names=[phonetic(w) for w in unknown],unknown=unknown,spelling_variants=variants)


def assess(field,left,right):
    if not left or not right:return None
    if field=='languages':
        a,b=language_set(left),language_set(right)
        equal=None if a is None or b is None else b<=a
        return dict(method=VERSION,status='needs_verification' if equal is None else 'equivalent' if equal else 'different',
                    equivalent=equal,left=sorted(a) if a else None,right=sorted(b) if b else None,
                    basis='Client languages must appear in DS-160; additional DS-160 languages are allowed.')
    if field not in FIELDS or not re.search('[\u0600-\u06ff]',str(left)+str(right)):return None
    if normal(left)==normal(right):
        return dict(method=VERSION,status='equivalent',equivalent=True,left=normal(left),right=normal(right),
                    basis='Identical wording after case, punctuation and Arabic spelling normalization.')
    a,b=terms(left),terms(right);x,y=set(a['concepts']),set(b['concepts'])
    equal=None;basis='Unknown wording needs translation verification; different scripts alone are not a mismatch.'
    if field in ('employer_name','hotel_name'):
        if Counter(a['names'])==Counter(b['names']) and any(a['names']) and (x-{'company'})==(y-{'company'}):
            equal=True;basis='Organization name transliteration and known business terms are compatible; not an authenticity check.'
    elif field=='education_name':
        if not a['unknown'] and not b['unknown']:
            core_x=x-{'faculty','physical_education','commerce','engineering','medicine','law'}
            core_y=y-{'faculty','physical_education','commerce','engineering','medicine','law'}
            if 'university' in core_x and core_x==core_y and len(core_x)>1:
                subjects={'physical_education','commerce','engineering','medicine','law'}
                sx,sy=x&subjects,y&subjects
                equal=not (sx and sy and sx!=sy)
                basis='Same named university; a supplied faculty is additional detail.' if equal else 'Known faculties differ at the same university.'
            elif 'university' in core_x and 'university' in core_y and len(core_x)>1 and len(core_y)>1:
                equal=False;basis='Known named universities differ.'
    elif field=='education_course':
        domains={'physical_education','accounting','commerce','engineering','medicine','law','computer_science'}
        dx,dy=x&domains,y&domains
        if x&{'handball','football'}:dx.add('physical_education')
        if y&{'handball','football'}:dy.add('physical_education')
        if not a['unknown'] and not b['unknown'] and dx and dy:
            equal=dx==dy
            # Shared broad domain does not erase contradictory specializations
            # or an explicitly different degree level.
            for detail in ({'handball','football'},{'bachelor','masters','doctorate'}):
                sx,sy=x&detail,y&detail
                if sx and sy and sx!=sy:equal=False
            basis='Degree and supplied specialization are compatible within the same educational domain.' if equal else 'Known educational domains differ.'
    elif not a['unknown'] and not b['unknown'] and x and y:
        equal=x==y;basis='Known Arabic/English terminology compared before literal text.'
    return dict(method=VERSION,status='needs_verification' if equal is None else 'compatible' if equal else 'different',
                equivalent=equal,left=a,right=b,basis=basis)
