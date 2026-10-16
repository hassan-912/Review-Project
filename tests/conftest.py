import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from extractor import VisaDocumentExtraction


@pytest.fixture
def complete_extraction():
    return VisaDocumentExtraction.model_validate({
        "passport":{"passport_number":"TEST12345","full_name":"MG TEST APPLICANT","given_names":"MG TEST","surname":"APPLICANT","date_of_birth":"1990-01-01","passport_issue":"2020-12-31","passport_expiry":"2030-12-31"},
        "visa_form":{"passport_number":"TEST12345","applicant_name":"MG TEST APPLICANT","date_of_birth":"1990-01-01","destination_country":"France","purpose_of_journey":"Tourism","intended_arrival":"2027-01-01","intended_departure":"2027-01-10"},
        "flight":{"departure_date":"2027-01-01","return_date":"2027-01-10","passenger_name":"MG TEST APPLICANT"},
        "hotel":[{"hotel_name":"Synthetic Paris Hotel","city":"Paris","check_in_date":"2027-01-01","check_out_date":"2027-01-06","guest_name":"MG TEST APPLICANT"},
                 {"hotel_name":"Synthetic Rome Hotel","city":"Rome","check_in_date":"2027-01-06","check_out_date":"2027-01-10","guest_name":"MG TEST APPLICANT"}],
        "insurance":{"insured_passport_number":"TEST12345","insured_name":"MG TEST APPLICANT","coverage_amount_eur":50000,"valid_from":"2027-01-01","valid_until":"2027-01-10"},
        "cover_letter":{"purpose_of_visit":"Tourism","funding_source":"Personal savings","ties_to_home_country":"Permanent employment and family","attached_documents_listed":True,"employer_mentioned":True},
        "employment":{"employer_name":"MG Synthetic Co","approved_leave_start":"2027-01-01","approved_leave_end":"2027-01-10","leave_approval_confirmed":True},
        "main_schengen_destination":"France","total_nights_per_country":{"France":5,"Italy":4},"travel_cities":["Paris","Rome"],
        "travel_plan":{"present":True,"start_date":"2027-01-01","end_date":"2027-01-10","cities":["Paris","Rome"],
            "days":[{"date":f"2027-01-{i:02d}","city":"Paris" if i<6 else "Rome","activities":["Confirmed fictional visit"],"transport":"Confirmed fictional transfer"} for i in range(1,11)]}
    })
