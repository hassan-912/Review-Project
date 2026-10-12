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
      'passport': 'FICTIONAL TEST PASSPORT - UTOPIA\n'+identity+'Expiry: 2031-04-15\nP<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F3104159ZE184226B<<<<<10',
      'visa_form': identity+'Purpose: Tourism\nMain destination: France\nArrival: 2027-01-01\nDeparture: 2027-01-10',
      'flight': identity+'Outbound: Cairo to Paris, 2027-01-01\nReturn: Rome to Cairo, 2027-01-10',
      'hotel': identity+'Booking 1: Synthetic Paris Hotel, Paris, France\nCheck-in: 2027-01-01\nCheck-out: 2027-01-06\nBooking 2: Synthetic Rome Hotel, Rome, Italy\nCheck-in: 2027-01-06\nCheck-out: 2027-01-10',
      'insurance': identity+'Insured Passport No.: L898902C3\nMedical coverage: EUR 50000\nValid from: 2027-01-01\nValid until: 2027-01-10\nTerritory: All Schengen countries',
      'cover_letter': identity+'I will visit France and Italy for tourism from 2027-01-01 to 2027-01-10.\nI fund the trip with personal savings. My family and permanent employment are in Egypt.\nEmployer: MG Synthetic Co. My approved leave is 2027-01-01 to 2027-01-10.\nAccommodation: Synthetic Paris Hotel and Synthetic Rome Hotel.\nAttachments: passport, visa form, flight, hotel, insurance, HR letter, travel plan.',
      'employment': identity+'Employer: MG Synthetic Co\nPosition: Accountant\nMonthly salary: EGP 25000\nPermanent contract\nHR approved annual leave: 2027-01-01 to 2027-01-10\nSigned and stamped leave approval',
      'travel_plan': identity+'Paris, France: 2027-01-01 to 2027-01-06 (5 nights)\nRome, Italy: 2027-01-06 to 2027-01-10 (4 nights)',
    }
    return {key:[(key+'.pdf',document(text))] for key,text in templates.items()}


if __name__=='__main__':
    language=sys.argv[1] if len(sys.argv)>1 else 'en'
    try:
        result=review_documents(setting('GEMINI_API_KEY'),synthetic_files(),AVAILABLE_MODELS[0],language,
                                lambda n:print('Stage',n,flush=True))
        extracted=result['extraction']
        assert len(extracted.hotel)==2,'The model must extract both hotel bookings'
        assert extracted.passport.passport_number=='L898902C3','Identity extraction failed'
        assert extracted.executive_summary,'Missing executive summary'
        print('LIVE REVIEW OK:',language,'model:',result['model_used'],'hotels:',len(extracted.hotel),
              'findings:',len(result['issues']),'score:',result['score'].score)
    except Exception as exc:
        # Do not print raw SDK errors, credentials, or document content.
        print('LIVE REVIEW FAILED:',type(exc).__name__)
        raise SystemExit(1)
