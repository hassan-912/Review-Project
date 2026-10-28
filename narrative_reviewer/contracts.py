"""Validated request and finding contracts for Gemini narrative review."""
from hashlib import sha256
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import VERSION


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Page(StrictModel):
    number: int = Field(ge=1)
    text: str = Field(max_length=18000)
    method: Literal['pdf_text', 'local_ocr', 'unreadable', 'extracted_fields', 'pdf_visual', 'native_text']
    provisional: bool = False


class Document(StrictModel):
    id: str = Field(pattern=r'^d[0-9]+$')
    filename: str = Field(max_length=300)
    categories: list[str] = Field(min_length=1, max_length=12)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    total_pages: int = Field(ge=1, le=150)
    pages: list[Page] = Field(max_length=150)
    context_mode: Literal['full_text', 'extracted_fields', 'extracted_text', 'pdf_visual'] = 'full_text'


class Citation(StrictModel):
    document_id: str = Field(pattern=r'^d[0-9]+$')
    page: int = Field(ge=1)
    quote: str = Field(min_length=4, max_length=1600)
    visual: bool = False


class PDFAttachment(StrictModel):
    document_id: str
    data: str = Field(max_length=28000000)


class VerifiedFact(StrictModel):
    field: str = Field(max_length=100)
    value: str = Field(max_length=1000)
    source: Citation


class Packet(StrictModel):
    version: Literal['narrative-v1'] = VERSION
    request_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    country: str = Field(max_length=40)
    language: Literal['en', 'ar'] = 'en'
    documents: list[Document] = Field(min_length=1, max_length=30)
    verified_facts: list[VerifiedFact] = Field(default_factory=list, max_length=180)
    limitations: list[str] = Field(default_factory=list, max_length=100)
    financial_context: dict = Field(default_factory=dict)
    attachments: list[PDFAttachment] = Field(default_factory=list,max_length=30)

    @model_validator(mode='after')
    def unique_sources(self):
        ids = [doc.id for doc in self.documents]
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate document IDs')
        for doc in self.documents:
            numbers = [page.number for page in doc.pages]
            if len(set(numbers)) != len(numbers) or any(n > doc.total_pages for n in numbers):
                raise ValueError('Invalid page inventory')
        import base64
        seen=set();size=0
        for attachment in self.attachments:
            doc=next((d for d in self.documents if d.id==attachment.document_id),None)
            if (not doc or doc.id in seen or not set(doc.categories)&{'bank_statement','supporting'} or
                    set(doc.categories)&{'passport','visa_form','hotel','flight','insurance','employment','cover_letter','travel_plan'}):
                raise ValueError('PDF attachment is not an allowed bank/supporting document')
            raw=base64.b64decode(attachment.data,validate=True);size+=len(raw)
            if not raw.startswith(b'%PDF-') or sha256(raw).hexdigest()!=doc.sha256:
                raise ValueError('PDF does not match the source document')
            seen.add(doc.id)
        if size>12*1024**2:raise ValueError('PDF context exceeds the inline request limit')
        if self.request_id != packet_digest(self.model_dump()):
            raise ValueError('Packet identity does not match its contents')
        return self


def packet_digest(payload):
    body = {key: value for key, value in payload.items() if key != 'request_id'}
    body.setdefault('financial_context',{});body.setdefault('attachments',[])
    return sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class Finding(StrictModel):
    section: Literal['cover_letter', 'travel_plan', 'bank_statement', 'supporting']
    kind: Literal['contradiction', 'coherence', 'clarity', 'unsupported_claim', 'needs_verification', 'translation_error']
    title: str = Field(min_length=3, max_length=180)
    explanation: str = Field(min_length=10, max_length=1800)
    suggestion: str = Field(min_length=5, max_length=1200)
    citations: list[Citation] = Field(min_length=1, max_length=6)
    action: Literal['remove','correct','verify'] = 'verify'


class SalaryMonth(StrictModel):
    month: str = Field(pattern=r'^\d{4}-\d{2}$')
    complete_month: bool
    status: Literal['matched','not_found','uncertain']
    matched_amount: float | None = Field(None,ge=0,allow_inf_nan=False)
    credited_date: str | None = None
    citations: list[Citation] = Field(default_factory=list,max_length=4)


class CreditDay(StrictModel):
    date: str
    amount: float = Field(gt=0,allow_inf_nan=False)
    citations: list[Citation] = Field(min_length=1,max_length=8)


class SalaryReference(StrictModel):
    amount: float = Field(gt=0,allow_inf_nan=False)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    basis: Literal['net','gross','unspecified']
    source: Citation


class BankAssessment(StrictModel):
    document_id: str
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    period_start: str
    period_end: str
    period_source: Citation
    holder_name: str | None = None
    owner_role: Literal['applicant','other','unknown'] = 'unknown'
    account_id: str | None = Field(None,max_length=80)
    bank_name: str | None = Field(None,max_length=100)
    account_source: Citation | None = None
    income_basis: Literal['employment','business','unknown'] = 'unknown'
    business_sources: list[Citation] = Field(default_factory=list,max_length=4)
    total_credits: float | None = Field(None,ge=0,allow_inf_nan=False)
    total_debits: float | None = Field(None,ge=0,allow_inf_nan=False)
    transaction_coverage: Literal['complete','partial','unreadable']
    closing_balance: float | None = Field(None,allow_inf_nan=False)
    balance_source: Citation | None = None
    salary_months: list[SalaryMonth] = Field(default_factory=list,max_length=6)
    large_credit_days: list[CreditDay] = Field(default_factory=list,max_length=8)


class CityEstimate(StrictModel):
    city: str = Field(max_length=80)
    days: int = Field(ge=1,le=180)
    daily_low_eur: float = Field(ge=0,le=5000,allow_inf_nan=False)
    daily_high_eur: float = Field(ge=0,le=5000,allow_inf_nan=False)
    source: Citation


class BudgetProposal(StrictModel):
    cities: list[CityEstimate] = Field(min_length=1,max_length=12)
    intercity_low_eur: float = Field(ge=0,le=20000,allow_inf_nan=False)
    intercity_high_eur: float = Field(ge=0,le=20000,allow_inf_nan=False)
    assumptions: str = Field(max_length=400)
    trip_start: str | None = None
    trip_end: str | None = None
    dates_sources: list[Citation] = Field(default_factory=list,max_length=4)


class Coverage(StrictModel):
    document_id: str = Field(pattern=r'^d[0-9]+$')
    page: int = Field(ge=1)
    status: Literal['reviewed', 'unreadable', 'not_reviewed']


class ModelReview(StrictModel):
    version: Literal['narrative-v1'] = VERSION
    request_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    status: Literal['complete', 'incomplete']
    findings: list[Finding] = Field(max_length=20)
    coverage: list[Coverage] = Field(max_length=300)
    limitations: list[str] = Field(max_length=30)
    bank_assessments: list[BankAssessment] = Field(default_factory=list,max_length=10)
    budget_proposal: BudgetProposal | None = None
    salary_reference: SalaryReference | None = None

    @model_validator(mode='after')
    def unique_coverage(self):
        keys = [(item.document_id,item.page) for item in self.coverage]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate page coverage')
        return self

