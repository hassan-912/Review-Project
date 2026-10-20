"""Trace findings to uploaded bytes and render real source regions in session memory."""
from collections import Counter
from io import BytesIO
import re
import pymupdf
from PIL import Image
from document_sources import source_is_grounded

ALIASES = {
    "full_name": {"full_name","applicant_name","passenger_name","guest_name","insured_name"},
    "passport_number": {"passport_number","insured_passport_number"},
    "start_date": {"start_date","intended_arrival","departure_date","check_in_date","valid_from","approved_leave_start"},
    "end_date": {"end_date","intended_departure","return_date","check_out_date","valid_until","approved_leave_end"},
}
DOCS = {"visa_form":("visa application","visa_form"),"passport":("passport",),"hotel":("hotel",),
        "appointment":("appointment",),
        "flight":("flight",),"insurance":("insurance",),"employment":("employment","hr"),
        "cover_letter":("cover letter","cover_letter"),"travel_plan":("travel itinerary","travel plan","travel_plan"),
        "national_id":("national id","national_id"),"supporting":("supporting",)}


def _normal(value):
    return re.sub(r"\s+"," ",str(value or "")).strip().casefold()


def _category(label):
    label=label.lower().split(" (")[0]
    return next((key for key,words in DOCS.items() if any(w in label for w in words)),None)


def _fields(field):
    names={field}
    for canonical,aliases in ALIASES.items():
        if field in aliases or field==canonical:
            names|=aliases
    if " vs " in field:
        for part in field.split(" vs "):
            names|=_fields(part.replace("flight ",""))
    return names


def attach_evidence(issues,data,uploaded_files):
    names=Counter(name for group in uploaded_files.values() for name,_ in group)
    categories={name:category for category,group in uploaded_files.items() for name,_ in group}
    kinds={audit.source_file:{_category(kind) for kind in audit.document_types} for audit in data.document_audits}
    for document in data.supporting_documents:
        kinds.setdefault(document.source_file,set()).add(_category(document.document_type))
    locations=[location.model_dump() for location in data.evidence_locations if names[location.source_file]==1]
    for document in data.supporting_documents:
        if names[document.source_file]!=1: continue
        for claim in document.claims:
            if claim.value and claim.page:
                locations.append({"source_file":document.source_file,"page":claim.page,"document":"supporting",
                    "field_name":claim.field_name,"value":claim.value,"text":claim.quote or claim.value,"box":None})
    for row in data.identity_evidence:
        if row.source_file and names[row.source_file]==1:
            for field in ("full_name","given_names","surname","passport_number","date_of_birth","passport_issue","passport_expiry","national_id_number","national_id_issue","national_id_expiry"):
                value=getattr(row,field,None)
                if value:
                    locations.append({"source_file":row.source_file,"page":row.page or 1,"document":row.document,
                        "field_name":field,"value":value,"text":value,"box":None})
    for issue in issues:
        category=_category(issue.document_name)
        allowed=_fields(issue.field_name)
        explicit = {name for name in names if name in issue.document_name}
        def matching(value, wanted):
            candidates=[loc for loc in locations if loc["field_name"] in allowed
                        and (not explicit or wanted != category or loc['source_file'] in explicit)
                        and (not wanted or categories.get(loc["source_file"])==wanted or _category(loc["document"])==wanted)]
            exact=[loc for loc in candidates if value and _normal(loc.get("value"))==_normal(value)]
            # A differently extracted field is not evidence of the asserted value.
            unique={}
            for loc in exact:
                unique.setdefault((loc["source_file"],loc["page"]),loc)
            return list(unique.values())[:2]
        issue.evidence=[loc for loc in issue.evidence if source_is_grounded(loc,uploaded_files)] or matching(issue.found_value,category)
        if not issue.evidence:
            # Explicitly a page preview, not an invented bounding box or confirmed error location.
            candidates=[name for name in names if names[name]==1 and
                        (name in explicit if explicit else category not in (None,'supporting') and categories[name]==category)]
            issue.evidence=[{"source_file":name,"page":1,"field_name":issue.field_name,"value":issue.found_value,
                             "text":issue.found_value or "","box":None,"preview":True} for name in candidates[:2]]
        reference=("appointment" if issue.message_key.startswith('appointment.') else "hotel" if issue.field_name=='destination_country' else "employment" if issue.message_key=="hr.window" else "national_id" if issue.field_name.startswith("national_id") else
                   "passport" if any(w in issue.field_name for w in ("name","passport","birth")) else "visa_form")
        issue.reference_evidence=[loc for loc in issue.reference_evidence if source_is_grounded(loc,uploaded_files)] or matching(issue.expected_value,reference)
        if not issue.affects_score and not issue.reference_evidence:
            continue
        if not issue.reference_evidence and not any(word in issue.field_name for word in ('name','passport','national_id','birth','date','start','end','arrival','departure','destination')):
            continue
        if not issue.reference_evidence:
            # A printed passport or HR/application page can still help the reviewer verify a correction.
            candidates=[loc for loc in locations if (categories.get(loc["source_file"])==reference or _category(loc["document"])==reference) and loc["field_name"] in allowed]
            issue.reference_evidence=candidates[:2]
        if not issue.reference_evidence:
            candidates=[name for name in names if names[name]==1 and (categories[name]==reference or reference in kinds.get(name,set()))]
            issue.reference_evidence=[{"source_file":name,"page":1,"field_name":issue.field_name,"value":issue.expected_value,
                "text":issue.expected_value,"box":None,"preview":True} for name in candidates[:1]]
    return issues


def render_source(location,uploaded_files):
    """Return PNG bytes and location method; never read a path supplied by a model."""
    matches=[(name,raw) for group in uploaded_files.values() for name,raw in group if name==location["source_file"]]
    if len(matches)!=1:
        return None
    name,raw=matches[0]
    page_number=location.get("page",1)
    if not isinstance(page_number,int) or page_number<1:
        return None
    quote=location.get("text") or location.get("value") or ""
    box=location.get("box")
    valid_box=isinstance(box,list) and len(box)==4 and all(isinstance(x,(int,float)) and 0<=x<=1 for x in box) and box[0]<box[2] and box[1]<box[3]
    if name.lower().endswith('.pdf'):
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            if page_number>len(doc): return None
            # Only search a different page when no trustworthy page location was extracted.
            pages=range(len(doc)) if location.get("preview") and quote else [page_number-1]
            for index in pages:
                page=doc[index]
                found=page.search_for(quote) if quote and len(quote.strip())>=2 and not location.get('layout') else []
                if found:
                    rect=pymupdf.Rect(found[0])
                    # A quote can span lines or table columns. Include every matched
                    # fragment so the crop contains the value as well as its label.
                    for fragment in found[1:]:
                        rect |= fragment
                    rect=pymupdf.Rect(rect.x0-65,rect.y0-35,rect.x1+65,rect.y1+35)&page.rect
                    pix=page.get_pixmap(matrix=pymupdf.Matrix(min(2,1200/max(rect.width,rect.height)),min(2,1200/max(rect.width,rect.height))),clip=rect,alpha=False)
                    return pix.tobytes('png'),index+1,'matched_region'
            page=doc[page_number-1]; rect=page.rect; method='page_preview'
            if valid_box and not location.get('preview'):
                rect=pymupdf.Rect(box[0]*rect.width,box[1]*rect.height,box[2]*rect.width,box[3]*rect.height)
                method='matched_region' if location.get('layout') else 'model_region'
            scale=min(2,1200/max(rect.width,rect.height))
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),clip=rect,alpha=False)
            return pix.tobytes('png'),page_number,method
    if page_number!=1: return None
    with Image.open(BytesIO(raw)) as source:
        source.load()
        method='page_preview'
        if valid_box and not location.get('preview'):
            source=source.crop((int(box[0]*source.width),int(box[1]*source.height),int(box[2]*source.width),int(box[3]*source.height)))
            method='model_region'
        source.thumbnail((1200,1200))
        output=BytesIO(); source.convert('RGB').save(output,format='PNG')
        return output.getvalue(),1,method
