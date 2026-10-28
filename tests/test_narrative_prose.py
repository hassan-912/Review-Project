import pytest
from narrative_reviewer.prose import prose_issues


@pytest.mark.parametrize('field,text,code',[
 ('explanation','This inaccurate claim contains申报.','unexpected_language'),
 ('suggestion','Align the dates. [M','unbalanced_brackets'),
 ('explanation','The letter says the applicant should','unfinished_sentence')])
def test_malformed_visible_advice_is_rejected(field,text,code):
    packet={'language':'en','documents':[{'pages':[{'text':'A current trip to Belgium.'}]}]}
    finding=dict(title='Dates differ',explanation='The dates conflict.',suggestion='Confirm and align them.')
    finding[field]=text
    assert any(row['code']==code for row in prose_issues(packet,[finding]))


def test_arabic_translation_feedback_can_show_corrected_english_values():
    packet={'language':'ar','documents':[{'pages':[{'text':'يناير / June'}]}]}
    finding=dict(kind='translation_error',title='ترجمة الشهر خاطئة',explanation='ورد الشهر خطأ في الترجمة.',
                 suggestion='استبدل June بكلمة January.')
    assert prose_issues(packet,[finding])==[]
