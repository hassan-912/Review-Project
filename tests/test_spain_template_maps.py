"""Reference-contract checks before accepting completed Spain forms."""
import json
from pathlib import Path

import pytest

from scripts.map_spain_templates import map_template

ROOT=Path(__file__).resolve().parents[1]/'templates'/'spain'


def load(name):
    return json.loads((ROOT/(name+'.json')).read_text(encoding='utf-8'))


def test_application_covers_every_number_with_cross_page_funding_and_distinct_identity_roles():
    data=load('schengen_application')
    fields={item['key']:item for item in data['fields']}
    assert {item['question_number'] for item in fields.values() if item['question_number']}==set(range(1,33))
    assert fields['travel_document.number']['question_number']==13
    assert fields['travel_document.number']['existing_review_field']=='visa_form.passport_number'
    assert fields['applicant.national_id_number']['question_number']==11
    assert fields['journey.intended_arrival']['question_number']==27
    assert fields['journey.intended_departure']['question_number']==27
    assert fields['journey.destination_member_states']['question_number']==25
    assert fields['journey.first_entry_member_state']['question_number']==26
    assert fields['funding.covered_by']['question_number']==32 and fields['funding.covered_by']['page']==3
    assert fields['eu_family_member.document_number']['subject_role']!='applicant'
    assert fields['guardian.surname']['subject_role']=='guardian'
    assert all(item['subject_role']=='official_use_only' for key,item in fields.items() if key.startswith('official.'))
    assert all(item['value'] is None for item in fields.values())


def test_blank_declaration_does_not_assume_applicant_is_bank_holder_or_invent_account_fields():
    data=load('bank_declaration')
    fields={item['key']:item for item in data['fields']}
    assert fields['applicant.full_name']['subject_role']=='applicant'
    assert fields['bank_holder.full_name']['subject_role']=='bank_holder'
    assert fields['bank_holder.passport_number']['subject_role']=='bank_holder'
    assert fields['declaration.place']['value']=='CAIRO'
    assert fields['declaration.place']['value_status']=='preprinted'
    assert fields['declaration.date']['value'] is None
    assert not any('account_number' in key or 'balance' in key for key in fields)


def test_id_translation_preserves_both_id_labels_and_month_only_date_support():
    fields={item['key']:item for item in load('national_id_translation')['fields']}
    assert fields['holder.front_id_number']['label']=='ID Number'
    assert fields['holder.full_id_number']['label']=='Full ID Number'
    assert fields['holder.front_id_number']['region_pdf_points']!=fields['holder.full_id_number']['region_pdf_points']
    assert fields['holder.issue_date']['value_type']=='date_or_year_month'
    assert not any('passport' in key for key in fields)


@pytest.mark.parametrize('name',['schengen_application','bank_declaration','national_id_translation'])
def test_values_export_matches_reference_fields_without_turning_blank_checks_into_no(name):
    data=load(name)
    assert len({item['key'] for item in data['fields']})==len(data['fields'])
    values=load('blank_values')[name]
    assert values=={item['key']:item['value'] for item in data['fields']}
    assert data['status']=='blank_template_mapped_awaiting_filled_sample'
    assert data['interactive_pdf_fields']==0
    for item in data['fields']:
        if item['options']:
            assert item['value'] is None
        x0,y0,x1,y1=item['region_normalized']
        assert 0<=x0<x1<=1 and 0<=y0<y1<=1
        assert 1<=item['page']<=data['pages']


def test_blank_mapper_rejects_changed_or_completed_source_instead_of_exporting_null(tmp_path):
    changed=tmp_path/'filled.pdf'
    changed.write_bytes(b'Different or completed PDF')
    with pytest.raises(ValueError,match='only maps the inspected blank reference'):
        map_template(changed,'schengen_application')
