"""One live review of fictional documents; never writes uploaded documents or secrets."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fpdf import FPDF
from fpdf.enums import XPos,YPos
from settings import setting
from extractor import AVAILABLE_MODELS
from review_pipeline import review_documents


def document(text):
    pdf=FPDF();pdf.add_page();pdf.set_font('Helvetica',size=11)
    for line in text.splitlines():
        pdf.multi_cell(0,6,line,new_x=XPos.LMARGIN,new_y=YPos.NEXT)
    return bytes(pdf.output())


def synthetic_files():
    identity='Name: ANNA MARIA ERIKSSON\nPassport: L898902C3\nBirth date: 1974-08-12\n'
    templates={
      'passport': 'FICTIONAL TEST PASSPORT - UTOPIA\n'+identity+'Given names: ANNA MARIA\nSurname: ERIKSSON\nIssue date: 2021-04-15\nExpiry: 2031-04-15\nP<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F3104159ZE184226B<<<<<10',
      'visa_form': identity+'Passport issue: 2021-04-15\nPassport expiry: 2031-04-15\nPurpose: Tourism\nMain destination: France\nArrival: 2027-01-01\nDeparture: 2027-01-10',
      'flight': identity+'Outbound: Cairo to Paris, 2027-01-01\nReturn: Rome to Cairo, 2027-01-10',
      'hotel': identity+'Booking 1: Synthetic Paris Hotel, Paris, France\nCheck-in: 2027-01-01\nCheck-out: 2027-01-06\nBooking 2: Synthetic Rome Hotel, Rome, Italy\nCheck-in: 2027-01-06\nCheck-out: 2027-01-10',
      'insurance': identity+'Insured Passport No.: L898902C3\nMedical coverage: EUR 50000\nValid from: 2027-01-01\nValid until: 2027-01-10\nTerritory: All Schengen countries',
      'cover_letter': identity+'I will visit France and Italy for tourism from 2027-01-01 to 2027-01-10.\nI fund the trip with personal savings. My family and permanent employment are in Egypt.\nEmployer: MG Synthetic Co. My approved leave is 2027-01-01 to 2027-01-10.\nAccommodation: Synthetic Paris Hotel and Synthetic Rome Hotel.\nAttachments: passport, visa form, flight, hotel, insurance, HR letter, travel plan.',
      'employment': identity+'Employer: MG Synthetic Co\nPosition: Accountant\nMonthly salary: EGP 25000\nPermanent contract\nHR approved annual leave: 2027-01-01 to 2027-01-10\nSigned and stamped leave approval',
      'travel_plan': identity+'Paris, France: 2027-01-01 to 2027-01-06 (5 nights)\nRome, Italy: 2027-01-06 to 2027-01-10 (4 nights)',
    }
    return {key:[(key+'.pdf',document(text))] for key,text in templates.items()}


def combined_typo_files():
    import pymupdf
    files=synthetic_files()
    def text(category):
        with pymupdf.open(stream=files[category][0][1],filetype='pdf') as pdf:
            return ''.join(page.get_text() for page in pdf)
    combined='COVER LETTER\n'+text('cover_letter')+'\nINSERT CLIENT NAME HERE\n\nTRAVEL PLAN\n'+text('travel_plan')
    files['cover_letter']=[('combined.pdf',document(combined))]
    del files['travel_plan']
    files['flight']=[('flight.pdf',document(text('flight').replace('ANNA MARIA ERIKSSON','ANNA MARIA ERIKSON').replace('L898902C3','L898902C8')))]
    files['visa_form']=[('visa_form.pdf',document(text('visa_form').replace('2031-04-15','2031-04-16')+'\nNational ID number: FICTIONAL-ID-123\nNational ID issue: 2022-02-03\nNational ID expiry: 2032-02-02'))]
    files['supporting']=[('national_id.pdf',document('FICTIONAL NATIONAL ID\nName: ANNA MARIA ERIKSSON\nNational ID number: FICTIONAL-ID-123\nIssue date: 2022-02-02\nExpiry: 2032-02-02'))]
    return files


if __name__=='__main__':
    language=sys.argv[1] if len(sys.argv)>1 else 'en'
    strict='--strict' in sys.argv
    try:
        result=review_documents(setting('GEMINI_API_KEY'),combined_typo_files() if strict else synthetic_files(),AVAILABLE_MODELS[0],language,
                                lambda n:print('Stage',n,flush=True))
        extracted=result['extraction']
        if '--save' in sys.argv:
            import json
            artifact=Path('output') / ('smoke-strict-'+language+'.json')
            artifact.parent.mkdir(exist_ok=True)
            artifact.write_text(json.dumps({'extraction':extracted.model_dump(),'issues':[i.model_dump(mode='json') for i in result['issues']],
                'writing':{k:[e.model_dump() for e in v] for k,v in result['writing'].items()}},ensure_ascii=False,indent=2),encoding='utf-8')
        assert len(extracted.hotel)==2,'The model must extract both hotel bookings'
        assert extracted.passport.passport_number=='L898902C3','Identity extraction failed'
        assert extracted.executive_summary,'Missing executive summary'
        if strict:
            assert extracted.cover_letter_text.present and extracted.travel_plan.present,'Combined sections not classified'
            assert 'combined.pdf' in extracted.cover_letter_text.source_files and 'combined.pdf' in extracted.travel_plan.source_files
            critical={i.field_name for i in result['issues'] if i.severity.value=='CRITICAL'}
            assert {'passport_number','passport_expiry','national_id_issue'}<=critical,'Identity typo checks missing'
            assert any(i.field_name in ('applicant_name','full_name') and i.severity.value=='CRITICAL' for i in result['issues'])
            assert any(e.original_text and 'INSERT CLIENT NAME HERE' in e.original_text for e in result['writing']['cover_letter']),'No specific template edit'
            assert result['writing']['travel_plan'],'Missing actionable travel-plan advice'
        print('LIVE REVIEW OK:',language,'model:',result['model_used'],'hotels:',len(extracted.hotel),
              'findings:',len(result['issues']),'score:',result['score'].score)
    except Exception as exc:
        # Do not print raw SDK errors, credentials, or document content.
        print('LIVE REVIEW FAILED:',type(exc).__name__)
        if isinstance(exc,AssertionError):
            print('Check:',str(exc))
        if hasattr(exc,'errors'):
            print('Schema errors:',[(e['loc'],e['type']) for e in exc.errors()])
        raise SystemExit(1)
