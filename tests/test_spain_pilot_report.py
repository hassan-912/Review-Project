from scripts.run_spain_pilot import describe_check,format_review_report,compare_package
import pytest


def test_mismatch_report_names_documents_and_preserves_both_dates():
    comparison={'checks':[
        {'check':'hotel.check_in_vs_application','status':'mismatch','found':'2030-06-12','expected':'2030-06-10'},
        {'check':'flight.outbound_vs_application','status':'mismatch','found':'2030-06-12','expected':'2030-06-10'},
        {'check':'application_vs_passport.name','status':'match','found':'Example Tester','expected':'Example Tester'},
    ]}
    result=format_review_report(comparison)
    assert '1 matched | 2 mismatched | 0 unverified' in result
    assert 'Hotel reservation check-in date does not match visa application intended arrival date.' in result
    assert 'Outbound flight departure date does not match visa application intended arrival date.' in result
    assert 'Hotel reservation check-in date: 2030-06-12' in result
    assert 'Visa application intended arrival date: 2030-06-10' in result
    assert 'Example Tester' not in result


def test_unreadable_value_is_reported_separately_from_mismatch():
    result=format_review_report({'checks':[
        {'check':'application_vs_passport.passport_number','status':'unverified','found':None,'expected':'X00001234'},
    ]})
    assert '0 matched | 0 mismatched | 1 unverified' in result
    assert 'COULD NOT VERIFY' in result
    assert 'Visa application passport number: Missing or unreadable' in result
    assert 'Passport number on passport: X00001234' in result
    assert 'MISMATCHES' not in result


def test_json_description_keeps_original_values_and_status():
    result=describe_check({'check':'application_vs_passport.passport_number',
                           'status':'mismatch','found':'X00001230','expected':'X00001234'})
    assert result['found']=='X00001230'
    assert result['expected']=='X00001234'
    assert result['status']=='mismatch'
    assert result['message']=='Visa application passport number does not match passport number on passport.'


@pytest.mark.parametrize('passport_id,translation_id,status,expected_check',[
    ('01234567890123','01234567890124','extracted','application_vs_passport.national_id_number'),
    (None,'01234567890124','extracted','application_vs_id_translation.national_id_number'),
    (None,'01234567890124','ambiguous','application_vs_id_translation.national_id_number'),
])
def test_pilot_national_id_reference_matches_website_policy(passport_id,translation_id,status,expected_check):
    forms={'schengen_application':dict(normalized_values={'applicant.national_id_number':'01234567890124'},
        fields=[dict(key='applicant.national_id_number',status='extracted')]),
        'national_id_translation':dict(normalized_values={'holder.full_id_number':translation_id},
        fields=[dict(key='holder.full_id_number',status=status)])}
    result=compare_package(forms,{}, {},dict(values={'national_id_number':passport_id}))
    check=next(row for row in result['checks'] if row['check']==expected_check)
    assert check['status']==('mismatch' if passport_id else 'match' if status=='extracted' else 'unverified')
    if passport_id:
        translation=next(row for row in result['checks'] if row['check']=='id_translation_vs_passport.national_id_number')
        assert translation['status']=='mismatch' and translation['expected']==passport_id
