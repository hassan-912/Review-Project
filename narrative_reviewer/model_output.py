"""Internal model output; request identity is bound by code, not copied by an LLM."""
from typing import Literal, Annotated

from pydantic import Field, model_validator

from .contracts import (Coverage,Finding,StrictModel,SalaryMonth,CreditDay,BankAssessment,CityEstimate,BudgetProposal,SalaryReference)

MAX_DRAFT_FINDINGS = 12


class PassageCitation(StrictModel):
    passage_id: str | None = Field(None,min_length=1,max_length=80)
    document_id: str | None = None
    page: int | None = Field(None,ge=1)
    quote: str | None = Field(None,min_length=4,max_length=1200)

    @model_validator(mode='after')
    def valid_reference(self):
        if self.passage_id:
            if self.document_id is not None or self.page is not None or self.quote is not None:
                raise ValueError('Use a passage ID or a visual citation, not both')
        elif not (self.document_id and self.page and self.quote):
            raise ValueError('Visual references require document, page and quote')
        return self


class DraftSalaryMonth(SalaryMonth):
    citations: list[PassageCitation] = Field(default_factory=list,max_length=4)


class DraftCreditDay(CreditDay):
    citations: list[PassageCitation] = Field(min_length=1,max_length=8)


class DraftBankAssessment(BankAssessment):
    period_source: PassageCitation
    balance_source: PassageCitation | None = None
    account_source: PassageCitation | None = None
    business_sources: list[PassageCitation] = Field(default_factory=list,max_length=4)
    salary_months: list[DraftSalaryMonth] = Field(default_factory=list,max_length=6)
    large_credit_days: list[DraftCreditDay] = Field(default_factory=list,max_length=8)


class DraftCityEstimate(CityEstimate):
    source: PassageCitation


class DraftBudgetProposal(BudgetProposal):
    cities: list[DraftCityEstimate] = Field(min_length=1,max_length=12)
    dates_sources: list[PassageCitation] = Field(default_factory=list,max_length=4)


class DraftSalaryReference(SalaryReference):
    source: PassageCitation


class DraftFinding(Finding):
    title: str = Field(min_length=3, max_length=100)
    explanation: str = Field(min_length=10, max_length=450)
    suggestion: str = Field(min_length=5, max_length=250)
    citations: list[PassageCitation] = Field(min_length=1, max_length=6)


class DraftReview(StrictModel):
    status: Literal['complete', 'incomplete']
    findings: list[DraftFinding] = Field(max_length=MAX_DRAFT_FINDINGS)
    coverage: list[Coverage] = Field(max_length=300)
    limitations: list[Annotated[str, Field(min_length=1, max_length=180)]] = Field(max_length=6)
    bank_assessments: list[DraftBankAssessment] = Field(default_factory=list,max_length=10)
    budget_proposal: DraftBudgetProposal | None = None
    salary_reference: DraftSalaryReference | None = None

    @model_validator(mode='after')
    def unique_coverage(self):
        keys = [(item.document_id, item.page) for item in self.coverage]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate page coverage')
        return self


def gemini_schema():
    """Send Gemini's supported JSON Schema subset; retain strict local validation."""
    supported={'$id','$defs','$ref','$anchor','type','format','enum',
               'items','prefixItems','minItems','maxItems','minimum','maximum','anyOf',
               'oneOf','properties','additionalProperties','required'}
    def clean(schema):
        result={}
        for key,value in schema.items():
            if key not in supported:continue
            if key in ('properties','$defs'):
                result[key]={name:clean(child) for name,child in value.items()}
            elif isinstance(value,dict):result[key]=clean(value)
            elif key in ('anyOf','oneOf','prefixItems'):result[key]=[clean(child) for child in value]
            else:result[key]=value
        return result
    return clean(DraftReview.model_json_schema())

