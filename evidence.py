"""Trace findings to uploaded bytes and render real source regions in session memory."""
from collections import Counter
from io import BytesIO
import re
import pymupdf
from PIL import Image, ImageDraw, ImageOps
from document_sources import source_is_grounded

ALIASES = {
    'hr.company_address': {'hr.company_address','employer_address'},
    'hr.company_name': {'hr.company_name','employer_name'},
    'hr.job_title': {'hr.job_title','occupation'},
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
        national_id_reference='passport' if data.passport.national_id_number and issue.field_name=='national_id_number' else 'national_id'
        reference=("visa_form" if issue.field_name.startswith('hr.') else "appointment" if issue.message_key.startswith('appointment.') else "hotel" if issue.field_name=='destination_country' else "employment" if issue.message_key=="hr.window" else national_id_reference if issue.field_name.startswith("national_id") else
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
                method='matched_region' if location.get('layout') or location.get('local_source') else 'model_region'
            scale=min(2,1200/max(rect.width,rect.height))
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),clip=rect,alpha=False)
            return pix.tobytes('png'),page_number,method
    if page_number!=1: return None
    with Image.open(BytesIO(raw)) as source:
        source.load()
        method='page_preview'
        if valid_box and not location.get('preview'):
            source=source.crop((int(box[0]*source.width),int(box[1]*source.height),int(box[2]*source.width),int(box[3]*source.height)))
            method='matched_region' if location.get('local_source') else 'model_region'
        source.thumbnail((1200,1200))
        output=BytesIO(); source.convert('RGB').save(output,format='PNG')
        return output.getvalue(),1,method


def _valid_region(box):
    return (isinstance(box,(list,tuple)) and len(box)==4
            and all(isinstance(value,(int,float)) and 0<=value<=1 for value in box)
            and box[0]<box[2] and box[1]<box[3])


def _marked_crop(source,regions,context,kind='incorrect'):
    """Show the complete field/row with a red finding or green reference marker."""
    crop_box=(max(0,int(context[0])-2),max(0,int(context[1])-2),
              min(source.width,int(context[2])+3),min(source.height,int(context[3])+3))
    cropped=source.convert('RGBA').crop(crop_box)
    overlay=Image.new('RGBA',cropped.size,(0,0,0,0))
    drawing=ImageDraw.Draw(overlay)
    fill,outline=((16,130,93,30),(11,104,74,255)) if kind=='correct' else ((220,38,38,30),(185,28,28,255))
    for x0,y0,x1,y1 in regions:
        drawing.rectangle((max(1,x0-crop_box[0]-3),max(1,y0-crop_box[1]-3),
                           min(cropped.width-2,x1-crop_box[0]+3),min(cropped.height-2,y1-crop_box[1]+3)),
                          fill=fill,outline=outline,width=3)
    marked=Image.alpha_composite(cropped,overlay).convert('RGB')
    marked.thumbnail((1400,900))
    output=BytesIO();marked.save(output,format='PNG')
    return output.getvalue()


def _pdf_field_context(page,regions,anchor=None):
    """Use enclosing table borders, otherwise show the complete labelled row."""
    target=pymupdf.Rect(regions[0])
    for region in regions[1:]:target|=region
    horizontal,vertical=[],[]
    def line(first,last):
        first,last=first*page.rotation_matrix,last*page.rotation_matrix
        if abs(first.y-last.y)<1:
            horizontal.append((first.y,min(first.x,last.x),max(first.x,last.x)))
        elif abs(first.x-last.x)<1:
            vertical.append((first.x,min(first.y,last.y),max(first.y,last.y)))
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0]=='l':line(item[1],item[2])
            elif item[0]=='re':
                rect=item[1]
                for first,last in ((rect.tl,rect.tr),(rect.tr,rect.br),(rect.br,rect.bl),(rect.bl,rect.tl)):
                    line(first,last)
    above=sorted((edge for edge in horizontal if edge[0]<=target.y0+2
                  and edge[1]<=target.x0+2 and edge[2]>=target.x1-2),reverse=True)[:8]
    below=sorted(edge for edge in horizontal if edge[0]>=target.y1-2
                 and edge[1]<=target.x0+2 and edge[2]>=target.x1-2)[:8]
    cells=[]
    for top in above:
        for bottom in below:
            height=bottom[0]-top[0]
            if not 20<=height<=page.rect.height*.45:continue
            sides=[edge for edge in vertical if edge[1]<=top[0]+2 and edge[2]>=bottom[0]-2]
            left=max((edge[0] for edge in sides if edge[0]<=target.x0+2),default=None)
            right=min((edge[0] for edge in sides if edge[0]>=target.x1-2),default=None)
            if left is None or right is None or right-left<70:continue
            if any(edge[1]>left+2 or edge[2]<right-2 for edge in (top,bottom)):continue
            cells.append(pymupdf.Rect(left,top[0],right,bottom[0]))
    if cells:return min(cells,key=lambda rect:rect.get_area())
    if anchor is not None:target|=anchor
    # Bookings and scans often have no table lines. Keep the entire row width
    # and its label above the value instead of a small value-centred snippet.
    return pymupdf.Rect(page.rect.x0,max(page.rect.y0,target.y0-65),
                        page.rect.x1,min(page.rect.y1,target.y1+45))


def _search_values(location):
    value=str(location.get('value') or '').strip()
    values=[value] if value else []
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        from datetime import date
        from calendar import month_name,month_abbr
        try:
            day=date.fromisoformat(value)
            for number in (str(day.day),f'{day.day:02d}'):
                values.extend(f'{number} {month} {day.year}' for month in (month_name[day.month],month_abbr[day.month]))
            values.extend(day.strftime(format) for format in ('%d/%m/%Y','%d.%m.%Y','%d-%m-%Y'))
        except ValueError:pass
    if quote:=location.get('text'):values.append(str(quote).strip())
    return list(dict.fromkeys(value for value in values if len(value)>=2))


_DATE_LABELS={
    'check_in_date':('check in','check-in','checkin'),
    'check_out_date':('check out','check-out','checkout'),
    'departure_date':('departure','departing','outbound'),
    'return_date':('return','inbound'),
    'intended_arrival':('intended arrival','date of arrival'),
    'intended_departure':('intended departure','date of departure'),
}


def _date_context_matches(page,rect,field):
    """Unlocated dates need a field label; policy dates never prove stay dates."""
    for block in page.get_text('blocks'):
        if block[6]==0 and (pymupdf.Rect(block[:4]) & rect).get_area()>0:
            if re.search(r'cancel|penalt|refund|policy|policies',block[4],re.I):return False
    labels=_DATE_LABELS.get(field)
    if labels is None:
        labels=tuple(label for choices in _DATE_LABELS.values() for label in choices)
    for label in labels:
        for anchor in page.search_for(label):
            vertical=rect.y0-anchor.y1
            same_line=rect.y0<=anchor.y1+2 and rect.y1>=anchor.y0-2
            if (same_line or 0<=vertical<=60) and abs(rect.x0-anchor.x0)<=130:
                return True
    return False


def render_error_region(location,uploaded_files,*,kind='incorrect'):
    """A real source crop with a field marker, or None when its position is unknown.

    Normalized local OCR/template boxes and native PDF text positions are the only
    location sources. Never fabricate a marker from a whole-page preview or read a path.
    """
    matches=[raw for group in uploaded_files.values() for name,raw in group
             if name==location.get('source_file')]
    page_number=location.get('page',1)
    if len(matches)!=1 or not isinstance(page_number,int) or page_number<1:return None
    raw=matches[0]
    if location.get('field_name')=='hotel_coverage_gap':return None
    box=location.get('box')
    local_box=(_valid_region(box) and not location.get('preview')
               and (location.get('local_source') or location.get('layout')))
    if location['source_file'].lower().endswith('.pdf'):
        with pymupdf.open(stream=raw,filetype='pdf') as document:
            if page_number>len(document):return None
            pages=range(len(document)) if location.get('preview') else [page_number-1]
            for index in pages:
                page=document[index]
                # Search coordinates are unrotated; normalized OCR boxes refer to
                # the displayed page. Work in displayed coordinates for both.
                anchor=pymupdf.Rect(box[0]*page.rect.width,box[1]*page.rect.height,
                                    box[2]*page.rect.width,box[3]*page.rect.height) if local_box else None
                regions=[]
                for value in _search_values(location):
                    found=page.search_for(value)
                    date_value=bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(location.get('value') or '')))
                    if anchor is None and date_value and (location.get('preview') or location.get('field_name') in _DATE_LABELS):
                        found=[rect for rect in found if _date_context_matches(page,rect,location.get('field_name'))]
                    found=[rect*page.rotation_matrix for rect in found]
                    if anchor is not None:
                        found=[rect for rect in found if (rect & anchor).get_area()>=rect.get_area()*.5]
                    if found:
                        regions=found;break
                if not regions and anchor is not None:regions=[anchor]
                if not regions:continue
                context=_pdf_field_context(page,regions,anchor)
                context=(context+(-.5,-.5,.5,.5))&page.rect
                scale=min(4,1400/context.width,900/context.height)
                pixmap=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),clip=context,alpha=False)
                source=Image.frombytes('RGB',(pixmap.width,pixmap.height),pixmap.samples)
                pixels=[(rect.x0*scale-pixmap.x,rect.y0*scale-pixmap.y,
                         rect.x1*scale-pixmap.x,rect.y1*scale-pixmap.y) for rect in regions]
                return _marked_crop(source,pixels,(0,0,source.width,source.height),kind),index+1,'matched_region'
        return None
    if page_number!=1 or not local_box:return None
    with Image.open(BytesIO(raw)) as original:
        source=ImageOps.exif_transpose(original).convert('RGB')
        pixels=[(box[0]*source.width,box[1]*source.height,box[2]*source.width,box[3]*source.height)]
        context=(0,max(0,pixels[0][1]-source.height*.12),source.width,
                 min(source.height,pixels[0][3]+source.height*.08))
        return _marked_crop(source,pixels,context,kind),1,'matched_region'
