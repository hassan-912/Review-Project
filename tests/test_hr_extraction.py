import pytest

from hr_extractor import (FIELDS,apply_hr_review,canonical,compare_hr_with_application,
                         make_hr_review_template,merge_hr_records,normalize_date,
                         normalize_money,parse_hr_lines)
from scripts.run_spain_pilot import format_review_report


def lines(*texts,method='pdf_text'):
    return [dict(text=text,page=1,method=method,confidence=None if method=='pdf_text' else .99,
                 region_normalized=[.1,.1+i*.025,.8,.12+i*.025]) for i,text in enumerate(texts)]


def record(name,*texts,method='pdf_text'):
    result=parse_hr_lines(lines(*texts,method=method),name)
    result.update(source_sha256='a'*64,pages=1)
    return result


def package():
    return merge_hr_records([
        record('salary.pdf','Employee name: Anna Tester','Employer: Example Hospital',
               'Net salary: 12,345.67','Currency: EGP'),
        record('leave.pdf','Employee name: Anna Tester',
               'Approved annual leave from 2030-06-01 to 2030-06-30.'),
        record('employment.pdf','Employee name: Anna Tester','Employer: Example Hospital',
               'Job title: Technician'),
    ])


def application(arrival='2030-06-10',departure='2030-06-20'):
    return dict(normalized_values={'applicant.given_names':'Anna','applicant.surname':'Tester',
        'employment_or_education.name':'Example Hospital','occupation.current':'Technician',
        'journey.intended_arrival':arrival,'journey.intended_departure':departure},fields=[])


def checks(hr,app=None):
    return {row['check']:row for row in compare_hr_with_application(hr,app or application())['checks']}


def test_split_letters_merge_by_field_with_provenance_and_leave_containment():
    hr=package()
    assert hr['values']['net_salary']=='12345.67'
    assert hr['values']['salary_currency']=='EGP'
    assert hr['values']['job_title']=='Technician'
    assert {source['source_file'] for source in hr['fields']['employee_name']['sources']}=={'salary.pdf','leave.pdf','employment.pdf'}
    assert all(row['status']=='match' for row in checks(hr).values())
    assert not any('salary' in row['check'] for row in compare_hr_with_application(hr,application())['checks'])


def test_one_combined_letter_produces_the_same_validation_inputs():
    hr=merge_hr_records([record('hr.pdf','Employee name: Anna Tester','Company name: Example Hospital',
        'Position: Technician','Leave start: 2030-06-01','Leave end: 2030-06-30','Leave is approved',
        'Net salary: 12,345.67','Currency: EGP')])
    assert all(hr['values'][key]==package()['values'][key] for key in FIELDS)
    assert all(row['status']=='match' for row in checks(hr).values())


def test_salary_and_signer_are_not_substituted_for_employee_or_employer():
    hr=merge_hr_records([record('hr.pdf','Bank: Fictional Bank','Signer: Manager Person','Net salary: 7000')])
    assert hr['values']['employee_name'] is None
    assert hr['values']['company_name'] is None
    assert all(row['status']=='unverified' for row in checks(hr).values())


@pytest.mark.parametrize('text',[
    'Leave request','Leave approval','Approved leave','Approved annual leave',
    'Approved leave start: 2030-06-01','Stamp and signature','اعتماد الرئيس المختص','طلب إجازة اعتيادية',
])
def test_headings_or_stamps_do_not_establish_approval(text):
    hr=merge_hr_records([record('leave.pdf',text)])
    assert hr['values']['leave_approved'] is None
    assert checks(hr)['hr.leave_approval']['status']=='unverified'


def test_explicit_refusal_is_a_mismatch_and_not_a_missing_value():
    hr=merge_hr_records([record('hr.pdf','Leave not approved')])
    row=checks(hr)['hr.leave_approval']
    assert row['status']=='mismatch'
    assert row['found'] is False


def test_high_ocr_confidence_does_not_silently_verify_handwritten_hr():
    hr=merge_hr_records([record('hr.pdf','Employee name: Anna Tester','Employer: Example Hospital',
        'Job title: Technician','Approved leave from 2030-06-01 to 2030-06-30',method='local_arabic_ocr')])
    assert hr['status']=='needs_verification'
    assert all(row['status']=='unverified' for row in checks(hr).values())


def test_conflicting_employees_are_not_merged_into_a_single_false_match():
    hr=package()
    hr=merge_hr_records([*hr['documents'],record('different.pdf','Employee name: Other Person')])
    assert hr['fields']['employee_name']['status']=='conflict'
    assert hr['values']['employee_name'] is None
    assert checks(hr)['hr.employee_name']['status']=='unverified'


@pytest.mark.parametrize(('start','end','status'),[
    ('2030-06-10','2030-06-20','match'),
    ('2030-06-11','2030-06-20','mismatch'),
    ('2030-06-01','2030-06-19','mismatch'),
    ('2030-06-20','2030-06-01','unverified'),
    ('2030-06-31','2030-06-30','unverified'),
])
def test_leave_must_cover_trip_and_have_a_valid_range(start,end,status):
    hr=merge_hr_records([record('hr.pdf',f'Leave start: {start}',f'Leave end: {end}')])
    row=checks(hr)['hr.leave_covers_trip']
    assert row['status']==status
    report=format_review_report({'checks':[row]})
    if status=='mismatch':assert 'HR leave dates do not cover the full application travel period.' in report


def test_cross_language_values_require_confirmation_instead_of_false_mismatch():
    hr=merge_hr_records([record('hr.pdf','اسم الموظف: مثال تجريبي','اسم الشركة: شركة تجريبية')])
    result=checks(hr)
    assert result['hr.employee_name']['status']=='unverified'
    assert result['hr.company_name']['status']=='unverified'


def test_provisional_application_employer_does_not_pass_as_confirmed():
    app=application();app['fields']=[dict(key='employment_or_education.name',status='needs_verification')]
    row=checks(package(),app)['hr.company_name']
    assert row['status']=='unverified'
    assert 'visa application employer field' in row['message']


@pytest.mark.parametrize('found,status',[('12 COMPANY STREET','match'),('99 Other Street','mismatch')])
def test_company_address_compares_with_employer_section_not_applicant_home(found,status):
    hr=merge_hr_records([record('hr.pdf','Company address: '+found)])
    app=application()
    app['normalized_values'].update({'employment_or_education.address':'12 Company Street',
                                    'applicant.contact.home_address':'99 Applicant Home Road'})
    row=checks(hr,app)['hr.company_address']
    assert row['status']==status and row['expected']=='12 Company Street'
    assert row['found']==found
    assert row['sources'][0]['source_file']=='hr.pdf'


@pytest.mark.parametrize('text',['Home address: 12 Home Street','Employee address: 12 Home Street','Address: 12 Unknown Street'])
def test_home_or_unlabelled_address_is_not_assumed_to_be_company_address(text):
    hr=merge_hr_records([record('hr.pdf',text)])
    assert hr['values']['company_address'] is None
    assert 'hr.company_address' not in checks(hr)


@pytest.mark.parametrize('method,application_status',[('local_arabic_ocr','extracted'),('pdf_text','ambiguous_shared_answer')])
def test_uncertain_company_address_needs_confirmation(method,application_status):
    hr=merge_hr_records([record('hr.pdf','Company address: 12 Company Street',method=method)])
    app=application();app['normalized_values']['employment_or_education.address']='99 Different Street'
    app['fields']=[dict(key='employment_or_education.address',status=application_status)]
    assert checks(hr,app)['hr.company_address']['status']=='unverified'


def test_conflicting_company_addresses_are_not_silently_selected():
    hr=merge_hr_records([record('one.pdf','Company address: 12 Company Street'),
                         record('two.pdf','Company address: 99 Different Street')])
    app=application();app['normalized_values']['employment_or_education.address']='12 Company Street'
    assert checks(hr,app)['hr.company_address']['status']=='unverified'


@pytest.mark.parametrize('label',["Company address","Employer's address","عنوان الشركة"])
def test_company_address_labels_preserve_arabic_address_and_normalize_digit_shapes(label):
    hr=merge_hr_records([record('hr.pdf',label+': ١٢ شارع الشركة')])
    app=application();app['normalized_values']['employment_or_education.address']='12 شارع الشركة'
    assert checks(hr,app)['hr.company_address']['status']=='match'


def test_manual_confirmation_is_bound_to_original_source_and_retains_ocr_evidence():
    hr=merge_hr_records([record('hr.pdf','Leave start: 2030-06-01',method='local_arabic_ocr')])
    review=make_hr_review_template(hr)
    review['fields']['leave_start']['confirmed']=True
    apply_hr_review(hr,review)
    assert hr['fields']['leave_start']['status']=='confirmed'
    assert hr['fields']['leave_start']['ocr_candidates']['status']=='needs_verification'
    assert hr['fields']['leave_start']['sources'][0]['method']=='manual_confirmation'


@pytest.mark.parametrize('change',['hash','page','date','boolean'])
def test_invalid_manual_confirmation_is_rejected(change):
    hr=package();review=make_hr_review_template(hr)
    key='leave_approved' if change=='boolean' else 'leave_start'
    review['fields'][key]['confirmed']=True
    if change=='hash':review['documents']['leave.pdf']='b'*64
    elif change=='page':review['fields'][key]['page']=2
    elif change=='date':review['fields'][key]['value']='2030-99-99'
    elif change=='boolean':review['fields'][key]['value']='true'
    with pytest.raises(ValueError):apply_hr_review(hr,review)


def test_arabic_digits_dates_and_amounts_normalize_without_invented_dates():
    assert normalize_date('٢١/١١/٢٠٣٠')=='2030-11-21'
    assert normalize_date('٢٠٣٠/١١/٢١')=='2030-11-21'
    assert normalize_date('٢٠٣٠١١٢١') is None
    assert normalize_date('01/02/30') is None
    assert normalize_money('٧،٤٣٧،٥٤')=='7437.54'
    assert canonical('الشركة')==canonical('الشركه')


def test_arabic_ocr_positions_can_be_saved_as_json(monkeypatch):
    import json
    from io import BytesIO
    from types import SimpleNamespace
    import offline_ocr
    np=pytest.importorskip('numpy')
    Image=pytest.importorskip('PIL.Image')
    result=SimpleNamespace(txts=['نص'],scores=[np.float32(.8)],
        boxes=np.array([[[0,0],[10,0],[10,10],[0,10]]],dtype=np.float32))
    monkeypatch.setattr(offline_ocr,'_arabic_engine',lambda:lambda _,**kwargs:result)
    image=Image.new('RGB',(20,20));raw=BytesIO();image.save(raw,format='PNG')
    encoded=json.dumps(offline_ocr.arabic_image_lines(raw.getvalue()))
    assert json.loads(encoded)[0]['region_normalized']==[0,0,.5,.5]


def test_arabic_salary_currency_and_inline_amount_are_kept_as_local_evidence():
    item=record('arabic-hr.pdf','صافي الراتب: ٢٠٬٠٠٠ جنيه مصري')
    fields={field['key']:field for field in item['fields']}
    assert fields['net_salary']['normalized_value']=='20000'
    assert fields['salary_currency']['normalized_value']=='EGP'
    assert fields['salary_currency']['sources'][0]['text']=='صافي الراتب: ٢٠٬٠٠٠ جنيه مصري'
