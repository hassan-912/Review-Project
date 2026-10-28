"""Map the three inspected BLANK Spain references; this does not read filled answers.

Run from the project root:
    python scripts/map_spain_templates.py --source-dir <folder> --output-dir templates/spain

Field regions were checked against every original page. Composite answers share a
region deliberately: field splitting, OCR and tick recognition await filled samples.
Do not run this against a completed form to extract values: use the future parser.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pymupdf


def field(key, label, page, rect, *, question=None, kind='text', options=None,
          role='applicant', condition=None, value=None, preprinted=False, shared=False):
    return dict(key=key, label=label, question_number=question, page=page,
                region_pdf_points=rect, value_type=kind, options=options or [],
                subject_role=role, condition=condition, value=value,
                value_status='preprinted' if preprinted else 'blank_in_reference',
                shared_answer_region=shared)


def schengen_fields():
    rows=[]
    def add(number,key,label,page,rect,**kwargs):
        rows.append(field(key,label,page,rect,question=number,**kwargs))
    def parts(number,prefix,label,page,rect,names,**kwargs):
        for name in names:
            add(number,prefix+'.'+name,label,page,rect,shared=True,**kwargs)
    add(1,'applicant.surname','Surname (Family name)',1,[48,198,450,236])
    add(2,'applicant.surname_at_birth','Surname at birth (Former family name(s))',1,[48,236,450,273])
    add(3,'applicant.given_names','First name(s) (Given name(s))',1,[48,273,450,310])
    add(4,'applicant.date_of_birth','Date of birth (day-month-year)',1,[48,310,182,393],kind='date')
    add(5,'applicant.place_of_birth','Place of birth',1,[182,310,316,338])
    add(6,'applicant.country_of_birth','Country of birth',1,[182,338,316,393])
    add(7,'applicant.current_nationality','Current nationality',1,[316,310,450,338])
    add(7,'applicant.nationality_at_birth','Nationality at birth, if different',1,[316,338,450,366])
    add(7,'applicant.other_nationalities','Other nationalities',1,[316,366,450,393],kind='text_list')
    add(8,'applicant.sex','Sex',1,[48,393,230,439],kind='single_choice',options=['Male','Female'])
    add(9,'applicant.marital_status','Marital status',1,[230,393,450,439],kind='single_choice',
        options=['Single','Married','Registered Partnership','Separated','Divorced','Widow(er)','Other'])
    add(9,'applicant.marital_status_other','Other (please specify)',1,[230,393,450,439],shared=True,condition='marital_status=Other')
    guardian_label="In the case of minors: parental authority/legal guardian (surname, first name, address, if different from applicant's, telephone number, e-mail address and nationality)"
    parts(10,'guardian',guardian_label,1,[48,439,450,514],
          ['surname','first_name','address','telephone','email','nationality'],role='guardian',condition='Applicant is a minor')
    add(11,'applicant.national_id_number','National identity number, where applicable',1,[48,514,450,542],kind='identifier')
    add(12,'travel_document.type','Type of travel document',1,[48,542,450,593],kind='single_choice',
        options=['Ordinary passport','Diplomatic passport','Service passport','Official passport','Special passport','Other travel document'])
    add(12,'travel_document.other_type','Other travel document (please specify)',1,[48,542,450,593],shared=True,condition='travel_document.type=Other travel document')
    add(13,'travel_document.number','Number of travel document',1,[48,593,168,630],kind='identifier')
    add(14,'travel_document.issue_date','Date of issue',1,[168,593,252,630],kind='date')
    add(15,'travel_document.expiry_date','Valid until',1,[252,593,331,630],kind='date')
    add(16,'travel_document.issuing_country','Issued by (country)',1,[331,593,450,630])
    family=dict(role='eu_eea_ch_family_member',condition='Qualifying EU, EEA or CH family member')
    add(17,'eu_family_member.surname','Surname (Family name)',1,[48,649,312,693],**family)
    add(17,'eu_family_member.given_names','First name(s) (Given name(s))',1,[312,649,450,693],**family)
    add(17,'eu_family_member.date_of_birth','Date of birth (day-month-year)',1,[48,693,182,733],kind='date',**family)
    add(17,'eu_family_member.nationality','Nationality',1,[182,693,312,733],**family)
    add(17,'eu_family_member.document_number','Number of travel documents or ID card',1,[312,693,450,733],kind='identifier',**family)
    add(18,'eu_family_member.relationship','Family relationship with an EU, EEA or CH citizen',1,[48,733,450,770],
        kind='single_choice',options=['spouse','child','grandchild','dependent ascendant','registered partnership','other'],**family)
    parts(19,'applicant.contact',"Applicant's home address and e-mail address",2,[48,57,249,112],['home_address','email'])
    add(19,'applicant.contact.telephones','Telephone number(s)',2,[249,57,545,112],kind='text_list')
    add(20,'residence.other_country','Residence in a country other than the country of current nationality',2,[48,112,545,164],kind='single_choice',options=['No','Yes'])
    parts(20,'residence', 'Yes. Residence permit or equivalent / Number / Valid until',2,[48,140,545,164],
          ['permit_type','permit_number','permit_valid_until'],condition='residence.other_country=Yes')
    exemption='Not required for qualifying EU, EEA or CH family members per this template footnote'
    add(21,'occupation.current','Current occupation',2,[48,164,545,192],condition=exemption)
    label="Employer and employer's address and telephone number. For students, name and address of educational establishment"
    parts(22,'employment_or_education',label,2,[48,192,545,220],['name','address','telephone'],condition=exemption)
    add(23,'journey.purposes','Main purpose(s) of the journey',2,[48,220,545,267],kind='multiple_choice',
        options=['Tourism','Business','Visiting family or friends','Cultural','Sports','Official visit','Medical reasons','Study','Airport transit','Other'])
    add(23,'journey.other_purpose','Other (please specify)',2,[48,220,545,267],shared=True,condition='journey.purposes includes Other')
    add(24,'journey.additional_information','Additional information on purpose of stay',2,[48,267,545,295])
    add(25,'journey.destination_member_states','Member State(s) of main destination (and other Member States of destination, if applicable)',2,[48,295,249,360],kind='text_list')
    add(26,'journey.first_entry_member_state','Member State of first entry',2,[249,295,545,360])
    add(27,'journey.entries_requested','Number of entries requested',2,[48,360,545,396],kind='single_choice',options=['Single entry','Two entries','Multiple entries'])
    add(27,'journey.intended_arrival','Intended date of arrival of the first intended stay in the Schengen area',2,[48,396,545,415],kind='date')
    add(27,'journey.intended_departure','Intended date of departure from the Schengen area after the first intended stay',2,[48,415,545,434],kind='date')
    add(28,'biometrics.previously_collected','Fingerprints collected previously for the purpose of applying for a Schengen visa',2,[48,434,545,452],kind='single_choice',options=['No','Yes'])
    add(28,'biometrics.collection_date','Date, if known',2,[48,452,194,480],kind='date',condition='biometrics.previously_collected=Yes')
    add(28,'biometrics.visa_sticker_number','Visa sticker number, if known',2,[194,452,545,480],kind='identifier',condition='biometrics.previously_collected=Yes')
    add(29,'final_destination_permit.issued_by','Entry permit for the final country of destination, where applicable / Issued by',2,[48,480,220,518],condition='Applicable final destination permit')
    add(29,'final_destination_permit.valid_from','Valid from',2,[220,499,337,518],kind='date',condition='Applicable final destination permit')
    add(29,'final_destination_permit.valid_until','until',2,[337,499,545,518],kind='date',condition='Applicable final destination permit')
    add(30,'host.person_or_accommodation_names','Surname and first name of the inviting person(s) in the Member State(s). If not applicable, name of hotel(s) or temporary accommodation(s) in the Member State(s)',2,[48,518,545,565],kind='text_list',role='host_or_accommodation',condition=exemption)
    parts(30,'host','Address and e-mail address of inviting person(s)/hotel(s)/temporary accommodation(s)',2,[48,565,249,630],
          ['address','email'],role='host_or_accommodation',condition=exemption)
    add(30,'host.telephone','Telephone number',2,[249,565,545,630],role='host_or_accommodation',condition=exemption)
    parts(31,'inviting_company','Name and address of inviting company/organisation',2,[48,630,545,654],['name','address'],role='inviting_company',condition=exemption)
    parts(31,'company_contact','Surname, first name, address and e-mail address of contact person in company/organisation',2,[48,654,249,719],
          ['surname','first_name','address','email'],role='company_contact',condition=exemption)
    add(31,'inviting_company.telephone','Telephone number of company/organisation',2,[249,654,545,719],role='inviting_company',condition=exemption)
    add(32,'funding.covered_by','Cost of travelling and living during the applicant\'s stay is covered',3,[48,57,545,168],
        kind='multiple_choice',options=['by the applicant himself/herself','by a sponsor (host, company, organisation)'],condition=exemption)
    add(32,'funding.additional_information','Additional answer beside question 32 heading',2,[48,719,545,738],
        condition=exemption)
    add(32,'funding.applicant.means_of_support','Means of support',3,[48,85,249,168],kind='multiple_choice',
        options=['Cash',"Traveller's cheques",'Credit card','Pre-paid accommodation','Pre-paid transport','Other'],condition=exemption)
    add(32,'funding.applicant.other_support','Other (please specify)',3,[48,140,249,168],condition=exemption,shared=True)
    add(32,'funding.sponsor.identity','by a sponsor (host, company, organisation), please specify',3,[249,57,545,103],condition=exemption,role='sponsor',shared=True)
    add(32,'funding.sponsor.reference','Sponsor reference',3,[249,75,545,103],kind='multiple_choice',
        options=['referred to in field 30 or 31','other'],condition=exemption,role='sponsor')
    add(32,'funding.sponsor.other_reference','other (please specify)',3,[249,85,545,103],condition=exemption,role='sponsor',shared=True)
    add(32,'funding.sponsor.means_of_support','Means of support',3,[249,103,545,168],kind='multiple_choice',
        options=['Cash','Accommodation provided','All expenses covered during the stay','Pre-paid transport','Other'],condition=exemption,role='sponsor')
    add(32,'funding.sponsor.other_support','Other (please specify)',3,[249,149,545,168],condition=exemption,role='sponsor',shared=True)
    rows.append(field('photo.present','PHOTO',1,[450,70,545,198],kind='image_presence'))
    for name in ['place','date']:
        rows.append(field('declaration.'+name,'Place and date',3,[48,635,297,699],kind='date' if name=='date' else 'text',shared=True))
    rows.append(field('declaration.signature_present','Signature (for minors, signature of parental authority/legal guardian)',3,[297,635,545,699],kind='signature_presence'))
    # Include the entire official-use column, without treating it as applicant data.
    official=[
        ('application_date','Date of application',[450,236,545,273],'date',[]),
        ('visa_application_number','Visa application number',[450,273,545,309],'identifier',[]),
        ('lodged_at','Application lodged at',[450,309,545,447],'single_choice',['Embassy/consulate','Service provider','Commercial intermediary','Border (Name)','Other']),
        ('border_name','Border (Name)',[450,355,545,410],'text',[]),
        ('lodged_at_other','Other',[450,410,545,447],'text',[]),
        ('file_handled_by','File handled by',[450,447,545,493],'text',[]),
        ('supporting_documents','Supporting documents',[450,493,545,595],'multiple_choice',['Travel document','Means of subsistence','Invitation','Means of transport','TMI','Other']),
        ('supporting_documents_other','Other',[450,558,545,595],'text',[]),
        ('visa_decision','Visa decision',[450,595,545,631],'single_choice',['Refused','Issued']),
        ('visa_types','Issued',[450,631,545,668],'multiple_choice',['A','C','LTV']),
        ('validity_marked','Valid',[450,668,545,677],'checkbox',[]),
        ('valid_from','From',[450,677,545,687],'date',[]),
        ('valid_until','Until',[450,687,545,705],'date',[]),
        ('number_of_entries','Number of entries',[450,705,545,733],'single_choice',['1','2','Multiple']),
        ('number_of_days','Number of days',[450,733,545,770],'integer',[]),
    ]
    rows.extend(field('official.'+key,label,1,rect,kind=kind,options=options,role='official_use_only')
                for key,label,rect,kind,options in official)
    return rows


def bank_fields():
    return [
        field('applicant.full_name','NOMBRE DEL SOLICITANTE DE VISADO / NAME OF THE VISA APPLICANT',1,[19,202,550,253]),
        field('bank_holder.full_name','NOMBRE Y APELLIDOS / NAME & SURNAME',1,[19,302,550,338],role='bank_holder'),
        field('bank_holder.passport_number','PASAPORTE Nº / PASSPORT NUMBER',1,[19,338,550,366],kind='identifier',role='bank_holder'),
        field('bank_holder.national_id_number','DOC. IDENTIDAD Nº / ID NUMBER',1,[19,370,550,400],kind='identifier',role='bank_holder'),
        field('declaration.place','Fecha Y LUGAR / DATE Y PLACE',1,[19,533,550,557],value='CAIRO',preprinted=True),
        field('declaration.date','Fecha Y LUGAR / DATE Y PLACE',1,[235,533,450,557],kind='date'),
        field('declaration.bank_signature_present','LA FIRMA BANCARIA / BANK SIGNATURE',1,[19,560,550,585],kind='signature_presence',role='bank_holder'),
    ]


def id_fields():
    return [
        field('holder.full_name','Full Name',1,[102,217,532,243],role='id_holder'),
        field('holder.address','Address',1,[102,243,532,268],role='id_holder'),
        field('holder.front_id_number','ID Number',1,[102,268,350,302],kind='identifier',role='id_holder'),
        field('holder.date_of_birth','Date of Birth',1,[350,268,532,302],kind='date',role='id_holder'),
        field('holder.full_id_number','Full ID Number',1,[102,470,400,496],kind='identifier',role='id_holder'),
        field('holder.issue_date','Issue Date',1,[400,470,532,496],kind='date_or_year_month',role='id_holder'),
        field('holder.current_job','Current Job',1,[102,496,532,523],role='id_holder'),
        field('holder.gender','Gender',1,[102,523,532,550],role='id_holder'),
        field('holder.religion','Religion',1,[102,550,532,576],role='id_holder'),
        field('holder.marital_status','Marital Status',1,[102,576,532,604],role='id_holder'),
        field('holder.expiry_date','Expiry Date',1,[102,604,532,636],kind='date_or_year_month',role='id_holder'),
    ]


TEMPLATES={
    'schengen_application':('Schengen_Application.pdf',3,schengen_fields),
    'bank_declaration':('Bank-Decleration.pdf',1,bank_fields),
    'national_id_translation':('National_ID_Translation.pdf',1,id_fields),
}

REFERENCE_SHA256={
    'schengen_application':'2970c8c3755cf1af37e6d75dd1cc50df00152126db05d59c51c36dbd3a75e525',
    'bank_declaration':'a219638c5f6e6ee2f3153dd65e85088748dc7d3c2ddc7c368d7be8d680f7fe5c',
    'national_id_translation':'7218223f04bdf852600971964d519b5f01e03afe8cdd7e9b9fc1399b5c1e7f2f',
}


def map_template(source, template_id):
    filename,pages,definition=TEMPLATES[template_id]
    raw=Path(source).read_bytes()
    if sha256(raw).hexdigest()!=REFERENCE_SHA256[template_id]:
        raise ValueError(f'{filename}: this command only maps the inspected blank reference. '
                         'A completed or different PDF must be tested with the filled-form parser, not mapped as blank.')
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        if len(pdf)!=pages:
            raise ValueError(f'{filename}: expected {pages} pages; got {len(pdf)}')
        fields=definition()
        baseline=[]
        for number,page in enumerate(pdf,1):
            lines=[]
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    text=''.join(span['text'] for span in line['spans']).strip()
                    if text:
                        lines.append(dict(text=text,region_pdf_points=[round(v,3) for v in line['bbox']]))
            checkboxes=[]
            for block in page.get_text('rawdict')['blocks']:
                for line in block.get('lines',[]):
                    chars=[char for span in line['spans'] for char in span['chars']]
                    starts=[i for i,char in enumerate(chars) if char['c']=='□']
                    for offset,start in enumerate(starts):
                        end=starts[offset+1] if offset+1<len(starts) else len(chars)
                        label=''.join(char['c'] for char in chars[start+1:end]).strip()
                        checkboxes.append(dict(label=label,region_pdf_points=[round(v,3) for v in chars[start]['bbox']]))
            baseline.append(dict(page=number,width=page.rect.width,height=page.rect.height,
                                 printed_text=page.get_text(sort=True),lines=lines,
                                 words=[dict(text=word[4],region_pdf_points=[round(v,3) for v in word[:4]])
                                        for word in page.get_text('words')],checkboxes=checkboxes,
                                 images=[dict(region_pdf_points=[round(v,3) for v in image['bbox']],digest=image['digest'].hex())
                                         for image in page.get_image_info(hashes=True)],
                                 drawings=[dict(region_pdf_points=[round(v,3) for v in drawing['rect']],
                                                signature=sha256(repr(drawing['items']).encode()).hexdigest())
                                           for drawing in page.get_drawings()]))
        for item in fields:
            page=pdf[item['page']-1]
            x0,y0,x1,y1=item['region_pdf_points']
            if not 0<=x0<x1<=page.rect.width or not 0<=y0<y1<=page.rect.height:
                raise ValueError('Field region outside page: '+item['key'])
            item['region_normalized']=[round(x0/page.rect.width,6),round(y0/page.rect.height,6),
                                       round(x1/page.rect.width,6),round(y1/page.rect.height,6)]
            item['baseline_region_text']=page.get_text(clip=pymupdf.Rect(item['region_pdf_points']),sort=True).strip()
        if len({item['key'] for item in fields})!=len(fields):
            raise ValueError('Duplicate canonical key')
        aliases={
            'travel_document.number':'visa_form.passport_number',
            'travel_document.issue_date':'visa_form.passport_issue',
            'travel_document.expiry_date':'visa_form.passport_expiry',
            'applicant.date_of_birth':'visa_form.date_of_birth',
            'applicant.national_id_number':'visa_form.national_id_number',
            'journey.intended_arrival':'visa_form.intended_arrival',
            'journey.intended_departure':'visa_form.intended_departure',
        } if template_id=='schengen_application' else {}
        for item in fields:
            if item['key'] in aliases:item['existing_review_field']=aliases[item['key']]
        return dict(schema_version=1,template_id='spain.'+template_id,country='Spain',
                    reference_filename=filename,reference_sha256=sha256(raw).hexdigest(),
                    pages=pages,interactive_pdf_fields=sum(len(list(page.widgets() or [])) for page in pdf),
                    status='blank_template_mapped_awaiting_filled_sample',
                    coordinate_system='PDF points, origin top-left; page is 1-based; normalized regions also included',
                    labels_note='Labels are normalized descriptions of the printed field or a component of a compound field; baseline_region_text preserves original wording.',
                    limitations=['These are values in the inspected blank reference, not extracted completed answers.',
                                 'Printed labels, declaration paragraphs and checkbox options are template text, never applicant values.',
                                 'A null checkbox/selection means no marked answer was observed in the blank reference.',
                                 'Shared answer regions require splitting after filled examples are inspected.',
                                 'Scanned/handwritten/flattened variants need OCR or visual checks; signatures are presence checks only.',
                                 'Never copy an answer from another document to fill a blank here.'],
                    fields=fields,baseline_pages=baseline)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=Path('templates/spain'))
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    values={}
    for template_id,(filename,_,_) in TEMPLATES.items():
        mapped=map_template(args.source_dir/filename,template_id)
        (args.output_dir/(template_id+'.json')).write_text(json.dumps(mapped,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        values[template_id]={item['key']:item['value'] for item in mapped['fields']}
        print(f'{template_id}: {mapped["pages"]} pages, {len(mapped["fields"])} keys, {mapped["interactive_pdf_fields"]} interactive fields')
    (args.output_dir/'blank_values.json').write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
