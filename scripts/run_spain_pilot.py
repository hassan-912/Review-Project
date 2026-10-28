"""Test provided Spain forms/bookings/passport locally without AI requests."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.extract_spain_forms import FILES
from spain_pdf_extractor import extract_spain_pdf,compare_spain_values
from booking_template_extractor import extract_hotel_v1,extract_flight_v1,name_matches
from passport_template_extractor import extract_egypt_passport,normalize_identifier


CHECK_LABELS={
    'application_vs_passport.passport_number':('Visa application passport number','Passport number on passport'),
    'application_vs_passport.date_of_birth':('Visa application date of birth','Passport date of birth'),
    'application_vs_passport.issue_date':('Visa application passport issue date','Passport issue date'),
    'application_vs_passport.expiry_date':('Visa application passport expiry date','Passport expiry date'),
    'application_vs_passport.place_of_birth':('Visa application place of birth','Passport place of birth'),
    'application_vs_passport.name':('Visa application applicant name','Passport holder name'),
    'application_vs_passport.national_id_number':('Visa application national ID number','National ID number printed on passport'),
    'application_vs_id_translation.national_id_number':('Visa application national ID number','National ID translation full ID number'),
    'id_translation_vs_passport.national_id_number':('National ID translation full ID number','National ID number printed on passport'),
    'hotel_vs_application.name':('Hotel reservation guest name','Visa application applicant name'),
    'hotel_vs_passport.name':('Hotel reservation guest name','Passport holder name'),
    'flight_vs_application.name':('Flight reservation traveller name','Visa application applicant name'),
    'flight_vs_passport.name':('Flight reservation traveller name','Passport holder name'),
    'hotel.check_in_vs_application':('Hotel reservation check-in date','Visa application intended arrival date'),
    'hotel.check_out_vs_application':('Hotel reservation check-out date','Visa application intended departure date'),
    'flight.outbound_vs_application':('Outbound flight departure date','Visa application intended arrival date'),
    'flight.return_vs_application':('Return flight departure date','Visa application intended departure date'),
    'flight.arrival_vs_hotel_check_in':('Outbound flight arrival date','Hotel reservation check-in date'),
}


def describe_check(check):
    if all(key in check for key in ('found_label','expected_label','message')):return dict(check)
    left,right=CHECK_LABELS.get(check['check'],(check['check']+' (found)','Reference value'))
    if check['status']=='mismatch':
        message=f'{left} does not match {right[0].lower()+right[1:]}.'
    elif check['status']=='match':
        message=f'{left} matches {right[0].lower()+right[1:]}.'
    else:
        message=f'Could not verify {left[0].lower()+left[1:]} against {right[0].lower()+right[1:]}; a required value is missing or unreadable.'
    return dict(check,found_label=left,expected_label=right,message=message)


def format_review_report(comparison):
    checks=[describe_check(check) for check in comparison['checks']]
    counts={status:sum(check['status']==status for check in checks)
            for status in ['match','mismatch','unverified']}
    lines=['Spain document comparison report',
           f"{counts['match']} matched | {counts['mismatch']} mismatched | {counts['unverified']} unverified",
           'Dates are shown as YYYY-MM-DD.','']
    for status,title in [('mismatch','MISMATCHES'),('unverified','COULD NOT VERIFY')]:
        issues=[check for check in checks if check['status']==status]
        if not issues:continue
        lines.append(title)
        for number,check in enumerate(issues,1):
            lines.append(f"{number}. {check['message']}")
            for label,value in [(check['found_label'],check.get('found')),
                                (check['expected_label'],check.get('expected'))]:
                display='Missing or unreadable' if value is None else str(value)
                lines.append(f'   {label}: {display}')
            lines.append('')
    if not counts['mismatch'] and not counts['unverified']:
        lines.append('All comparison checks matched.')
    lines.append('Check the original documents and correct the inconsistent value; a mismatch alone does not identify which document is wrong.')
    return '\n'.join(lines)+'\n'


def compare_package(forms,hotel,flight,passport):
    app=forms['schengen_application'].get('normalized_values',{})
    reference=passport.get('values',{})
    hotel_values=hotel.get('values',{});flight_values=flight.get('values',{})
    checks=[]
    def compare(key,found,expected,*,name=False,given=None,surname=None):
        if name:
            matched=name_matches(found,given,surname)
        else:
            matched=None if found is None or expected is None else str(found).strip().casefold()==str(expected).strip().casefold()
        checks.append(describe_check(dict(check=key,status='unverified' if matched is None else 'match' if matched else 'mismatch',
                           found=found,expected=expected)))
    for app_key,passport_key in [('travel_document.number','passport_number'),('applicant.date_of_birth','date_of_birth'),
        ('travel_document.issue_date','issue_date'),('travel_document.expiry_date','expiry_date'),('applicant.place_of_birth','place_of_birth')]:
        compare('application_vs_passport.'+passport_key,app.get(app_key),reference.get(passport_key))
    app_given=app.get('applicant.given_names');app_surname=app.get('applicant.surname')
    app_name=' '.join(value for value in (app_given,app_surname) if value) or None
    compare('application_vs_passport.name',app_name,reference.get('full_name'),name=True,
            given=reference.get('given_names'),surname=reference.get('surname'))
    def verified_id(form,key):
        field=next((row for row in form.get('fields',[]) if row['key']==key),{})
        return form.get('normalized_values',{}).get(key) if field.get('status') in ('extracted','confirmed') else None
    id_number=verified_id(forms.get('national_id_translation',{}),'holder.full_id_number')
    passport_id=reference.get('national_id_number')
    app_id=verified_id(forms['schengen_application'],'applicant.national_id_number')
    if any((app_id,id_number,passport_id)):
        suffix='passport' if passport_id else 'id_translation'
        compare('application_vs_'+suffix+'.national_id_number',normalize_identifier(app_id) if app_id else None,
                normalize_identifier(passport_id or id_number) if passport_id or id_number else None)
        if passport_id and id_number:
            compare('id_translation_vs_passport.national_id_number',normalize_identifier(id_number),normalize_identifier(passport_id))
    for label,name in [('hotel',hotel_values.get('reserved_for')),('flight',flight_values.get('traveller_name'))]:
        compare(label+'_vs_application.name',name,app_name,name=True,given=app_given,surname=app_surname)
        compare(label+'_vs_passport.name',name,reference.get('full_name'),name=True,
                given=reference.get('given_names'),surname=reference.get('surname'))
    for label,found,expected in [
        ('hotel.check_in_vs_application',hotel_values.get('check_in_date'),app.get('journey.intended_arrival')),
        ('hotel.check_out_vs_application',hotel_values.get('check_out_date'),app.get('journey.intended_departure')),
        ('flight.outbound_vs_application',flight_values.get('outbound_departure_date'),app.get('journey.intended_arrival')),
        ('flight.return_vs_application',flight_values.get('return_departure_date'),app.get('journey.intended_departure')),
        ('flight.arrival_vs_hotel_check_in',flight_values.get('outbound_arrival_date'),hotel_values.get('check_in_date')),
    ]:compare(label,found,expected)
    return dict(checks=checks,limitations=[
        'Booking names accept exact full given names + surname OR first given name + the complete surname; no fuzzy spelling correction.',
        'Flight dates/times are local as printed. This direct-flight pilot does not resolve overnight/transit itineraries.',
        'Bank-holder and applicant identity remain separate; no ownership is inferred from a matching identifier.',
    ])


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--passport',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=Path('output/spain_pilot'))
    parser.add_argument('--hr',type=Path,nargs='+',help='One combined HR letter or multiple salary/leave/employment PDFs.')
    parser.add_argument('--hr-language',choices=['ar','en'],default='ar')
    parser.add_argument('--hr-reviewed-values',type=Path,help='Confirmed HR values bound to the input document hashes.')
    args=parser.parse_args()
    required_files=[args.source_dir/name for name in FILES.values()]
    required_files.extend([args.source_dir/'hotel.pdf',args.source_dir/'flight.pdf',args.passport])
    required_files.extend(args.hr or [])
    if args.hr_reviewed_values:
        if not args.hr:parser.error('--hr-reviewed-values requires --hr input PDFs.')
        required_files.append(args.hr_reviewed_values)
    missing=[path for path in required_files if not path.is_file()]
    if missing:
        parser.error('Missing input file(s):\n'+'\n'.join(f'  {path}' for path in missing)+
                     '\nUse the actual PDF folder for --source-dir and the actual passport image file for --passport.')
    try:
        raw_inputs={path:path.read_bytes() for path in required_files}
    except OSError as error:
        parser.error(f'Could not read input: {error}. Check that the files are available and rerun.')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    forms={}
    for template,name in FILES.items():
        forms[template]=extract_spain_pdf(raw_inputs[args.source_dir/name],template,name)
        print(template,forms[template]['status'],flush=True)
    hotel=extract_hotel_v1(raw_inputs[args.source_dir/'hotel.pdf'],'hotel.pdf')
    print('hotel',hotel['status'],flush=True)
    flight=extract_flight_v1(raw_inputs[args.source_dir/'flight.pdf'],'flight.pdf')
    print('flight',flight['status'],flush=True)
    passport=extract_egypt_passport(raw_inputs[args.passport],args.passport.name)
    print('passport',passport['status'],flush=True)
    comparison=compare_package(forms,hotel,flight,passport)
    hr=None
    if args.hr:
        from hr_extractor import extract_hr_documents,compare_hr_with_application,make_hr_review_template
        try:
            reviewed=json.loads(raw_inputs[args.hr_reviewed_values].decode('utf-8-sig')) if args.hr_reviewed_values else None
            hr=extract_hr_documents([(path.name,raw_inputs[path]) for path in args.hr],args.hr_language,reviewed)
        except (ValueError,ImportError) as error:parser.error(f'HR extraction: {error}')
        hr_comparison=compare_hr_with_application(hr,forms['schengen_application'])
        comparison['checks'].extend(hr_comparison['checks'])
        comparison['limitations'].extend(hr_comparison['notes'])
        (args.output_dir/'hr_review_template.json').write_text(json.dumps(make_hr_review_template(hr),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('HR',hr['status'],flush=True)
    report=dict(ai_requests=0,forms=forms,hotel=hotel,flight=flight,passport=passport,
                comparisons=comparison,form_consistency=compare_spain_values(forms),
                limitations=['This is an offline pilot for the supplied templates, not a replacement of the live review pipeline.',
                             'An extracted status is a transcription result, not a statement of document authenticity.'])
    values=dict(forms={key:value.get('filled_values',{}) for key,value in forms.items()},hotel=hotel.get('values',{}),
                flight=flight.get('values',{}),passport=passport.get('values',{}))
    if hr is not None:
        report['hr']=hr;values['hr']=hr['values']
    for name,data in [('extraction_evidence.json',report),('filled_values.json',values),('comparisons.json',comparison)]:
        (args.output_dir/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    readable_report=format_review_report(comparison)
    report_path=args.output_dir/'review_report.txt'
    report_path.write_text(readable_report,encoding='utf-8')
    print('\n'+readable_report,flush=True)
    print(f'AI requests=0. Report saved to: {report_path.resolve()}',flush=True)


if __name__=='__main__':main()
