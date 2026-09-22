"""Session 3 labeled test set — raw case definitions.

Every entity value here is synthetic. PAN and Aadhaar numbers are
constructed to match the real format (Aadhaar with a genuine Verhoeff
checksum, computed programmatically below, not typed by hand) but are not
real, issued identifiers. Names, emails, and phone numbers are invented.

Each case is (category, text, entities), where `entities` lists
(EntityType-value, exact substring) pairs IN THE ORDER they appear in
`text`. build_labeled_set.py locates each substring by sequential search
and computes character offsets — offsets are never hand-counted, which is
the whole point: a labeling mistake here is a find()-miss or an assertion
failure at build time, not a silent off-by-one in a hand-typed number.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from pii_redaction.detectors.verhoeff import generate_check_digit
from tests.fixtures import synthetic_aadhaar

# ---------------------------------------------------------------------------
# Synthetic Aadhaar pool — 20 valid-checksum, fake numbers. First digit is
# 2-9 per UIDAI spec; enforced by synthetic_aadhaar()'s own validation.
# ---------------------------------------------------------------------------
_AADHAAR_BASES = [
    "23456789012", "34567890123", "45678901234", "56789012345",
    "67890123456", "78901234567", "89012345678", "90123456789",
    "24681357902", "35792468013", "46813579024", "57924680135",
    "68035791246", "79146802357", "80257913468", "91368024579",
    "22334455667", "33445566778", "44556677889", "55667788990",
]
for _b in _AADHAAR_BASES:
    assert len(_b) == 11 and _b[0] in "23456789", f"bad base {_b}"

AADHAAR_POOL = [synthetic_aadhaar(b) for b in _AADHAAR_BASES]


def grouped(aadhaar: str) -> str:
    """Format as UIDAI's conventional 4-4-4 grouping."""
    return f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}"


def corrupt(aadhaar: str, position: int = 5) -> str:
    """Flip one digit. Verhoeff detects every single-digit substitution
    error, so this is guaranteed to produce an invalid checksum — used for
    near-miss negatives, never as a claimed-valid Aadhaar number."""
    digits = list(aadhaar)
    digits[position] = str((int(digits[position]) + 1) % 10)
    return "".join(digits)


# Sanity-check the corruption guarantee actually holds, at import time.
from pii_redaction.detectors.verhoeff import validate as _verhoeff_validate  # noqa: E402

for _a in AADHAAR_POOL:
    assert _verhoeff_validate(_a)
    assert not _verhoeff_validate(corrupt(_a))

P = AADHAAR_POOL  # short alias used throughout the case list below

# ---------------------------------------------------------------------------
# Synthetic PAN pool — one per CBDT holder-type code, structurally valid,
# not real issued identifiers.
# ---------------------------------------------------------------------------
PAN = {
    "P": "AXZPK4521F",  # Individual
    "C": "BNTCX7788Q",  # Company
    "H": "PLMHZ3456K",  # HUF
    "F": "QWEFR9012L",  # Firm/LLP
    "T": "MZXTB6789N",  # Trust
    "A": "RTYAL2345P",  # Association of Persons
    "B": "UIOBK5678R",  # Body of Individuals
    "G": "ASDGM1234T",  # Government
    "L": "FGHLJ7890V",  # Local Authority
    "J": "NBVJH4321S",  # Artificial Juridical Person
}
# A structurally-invalid PAN (4th char 'Z' / 'I' are not real holder codes)
# for the near-miss negatives — must never appear as a gold PAN entity.
INVALID_HOLDER_PANS = ["AAAZX5678Q", "BBBIY1234M"]

CASES: list[tuple[str, str, list[tuple[str, str]]]] = []


def add(category: str, text: str, entities: list[tuple[str, str]]) -> None:
    CASES.append((category, text, entities))


# ============================== PERSON — regional/community diversity =====

_north = [
    "Rahul Sharma", "Priya Gupta", "Aditya Verma", "Sneha Mishra",
    "Vikram Chauhan", "Neha Agarwal", "Rohan Kapoor", "Anjali Saxena",
]
_north_sentences = [
    "{} submitted his KYC documents for verification.",
    "{} requested an update on her loan application status.",
    "{} was assigned as the primary contact for the account.",
    "{} flagged a discrepancy in the March invoice.",
    "{} approved the vendor onboarding request.",
    "{} escalated the support ticket to level two.",
    "{} completed the compliance training module.",
    "{} reviewed the quarterly audit findings.",
]
for _name, _tmpl in zip(_north, _north_sentences):
    add("person_north_indian", _tmpl.format(_name), [("PERSON", _name)])

_south = [
    "Venkataraman Subramaniam", "Lakshmi Narayanan", "Karthik Iyer",
    "Deepa Krishnamurthy", "Srinivasan Raghavan", "Meenakshi Sundaram",
    "Arjun Reddy", "Divya Chandrasekaran",
]
_south_sentences = [
    "{} signed off on the merger documents.",
    "{} is the designated data protection officer for this unit.",
    "{} raised a concern about the consent form wording.",
    "{} transferred to the risk management team.",
    "{} will present the findings at the review meeting.",
    "{} closed the incident ticket yesterday.",
    "{} updated the customer's billing preferences.",
    "{} was interviewed for the analyst position.",
]
for _name, _tmpl in zip(_south, _south_sentences):
    add("person_south_indian", _tmpl.format(_name), [("PERSON", _name)])

_muslim = [
    "Mohammed Irfan Khan", "Ayesha Siddiqui", "Zainab Rahman",
    "Imran Qureshi", "Fatima Sheikh", "Aamir Hussain",
]
_muslim_sentences = [
    "{} confirmed receipt of the settlement letter.",
    "{} filed a grievance regarding delayed reimbursement.",
    "{} is listed as the emergency contact on file.",
    "{} requested access to the shared drive.",
    "{} completed the exit interview this morning.",
    "{} was promoted to team lead last quarter.",
]
for _name, _tmpl in zip(_muslim, _muslim_sentences):
    add("person_muslim", _tmpl.format(_name), [("PERSON", _name)])

_christian = ["Maria Fernandes", "Paul D'Souza", "Jerry Pinto", "Thomas Kurian", "Sarah Thomas"]
_christian_sentences = [
    "{} coordinated the vendor site visit.",
    "{} reported a data access anomaly.",
    "{} submitted the reimbursement claim late.",
    "{} reviewed the data retention policy draft.",
    "{} onboarded three new hires this week.",
]
for _name, _tmpl in zip(_christian, _christian_sentences):
    add("person_christian", _tmpl.format(_name), [("PERSON", _name)])

_sikh = ["Gurpreet Singh", "Harpreet Kaur", "Manjeet Singh", "Simran Kaur", "Jaspreet Bhatia"]
_sikh_sentences = [
    "{} authorized the wire transfer.",
    "{} was assigned the internal audit for Q3.",
    "{} flagged the vendor contract for legal review.",
    "{} updated her mailing address in the portal.",
    "{} handled the customer escalation call.",
]
for _name, _tmpl in zip(_sikh, _sikh_sentences):
    add("person_sikh", _tmpl.format(_name), [("PERSON", _name)])

_common_word_names = [
    ("Akash Mehta", "{} booked the conference room for Friday."),
    ("Hope Fernandez", "{} called about the delayed shipment."),
    ("Joy Mathew", "{} submitted his resignation letter."),
    ("Rose D'Cruz", "{} processed the refund request."),
    ("Sunny Malhotra", "{} confirmed the meeting for Tuesday."),
    ("Happy Singh", "{} renewed the annual maintenance contract."),
    ("Raj Kumar Yadav", "{} verified the shipment manifest."),
    ("Precious Lobo", "{} scheduled the onboarding session."),
]
for _name, _tmpl in _common_word_names:
    add("person_common_word_name", _tmpl.format(_name), [("PERSON", _name)])

# ============================== EMAIL =======================================

_emails = [
    "Please send the report to priya.sharma@examplecorp.com by Friday.",
    "The support ticket was raised from ops+urgent@vendorhub.in.",
    "Reset password instructions were sent to r.verma@company.co.in.",
    "cc: legal.team@corporate-group.org on all future correspondence.",
    "Escalations should go to helpdesk@support.examplebank.com.",
    "Her personal email k.iyer1990@gmail.com was used for the registration.",
    "Invoices are auto-forwarded to billing@finance.acmeindia.net.",
    "The whistleblower report came in through anon.tip@ethicsline.co.",
]
_email_values = [
    "priya.sharma@examplecorp.com", "ops+urgent@vendorhub.in",
    "r.verma@company.co.in", "legal.team@corporate-group.org",
    "helpdesk@support.examplebank.com", "k.iyer1990@gmail.com",
    "billing@finance.acmeindia.net", "anon.tip@ethicsline.co",
]
for _text, _val in zip(_emails, _email_values):
    add("email", _text, [("EMAIL", _val)])

# ============================== PHONE =======================================

_phones = [
    ("Call the customer at 9876543210 to confirm delivery.", "9876543210"),
    ("Her registered mobile number is +91 98765 43210.", "+91 98765 43210"),
    ("Reach the vendor on +91-8123456789 for urgent issues.", "+91-8123456789"),
    ("The alternate contact number is 07012345678.", "07012345678"),
    ("SMS the OTP to 99887 76655 once verified.", "99887 76655"),
    ("His work line is +91 7000012345 during business hours.", "+91 7000012345"),
    ("The courier confirmed delivery to 6123456780.", "6123456780"),
    ("Please update the number on file to +91-9988776655.", "+91-9988776655"),
    ("Landline extension aside, her cell is 08234567891.", "08234567891"),
    ("The registered number 9345678123 bounced back twice.", "9345678123"),
]
for _text, _val in _phones:
    add("phone", _text, [("PHONE", _val)])

# ============================== PAN ==========================================

_pan_sentences = [
    ("P", "His individual PAN {} is on file for tax purposes."),
    ("C", "The corporate PAN {} was used for the invoice."),
    ("H", "HUF account PAN {} needs to be re-verified."),
    ("F", "The partnership firm's PAN {} was rejected by the bank."),
    ("T", "Trust PAN {} is linked to the donation account."),
    ("A", "The AOP's PAN {} was flagged for review."),
    ("B", "Body of Individuals PAN {} is pending activation."),
    ("G", "Government entity PAN {} was updated in the system."),
    ("L", "Local authority PAN {} requires re-submission."),
    ("J", "The juridical person's PAN {} was cross-checked."),
]
for _code, _tmpl in _pan_sentences:
    _val = PAN[_code]
    add("pan", _tmpl.format(_val), [("PAN", _val)])

# ============================== AADHAAR ======================================

_aadhaar_cases = [
    (P[6], True, "Her Aadhaar number {} was linked to the mobile wallet."),
    (P[7], True, "Aadhaar {} was submitted for the subsidy application."),
    (P[8], False, "UID {} is registered against the ration card."),
    (P[9], True, "The applicant's Aadhaar number is {}."),
    (P[10], False, "Aadhaar verification failed for {} due to a mismatch."),
    (P[11], True, "Please update the Aadhaar {} linked to this account."),
    (P[12], False, "Aadhaar number {} was used for e-KYC."),
    (P[13], True, "The beneficiary's Aadhaar {} is pending seeding."),
    (P[14], True, "Aadhaar {} appears twice in the deduplication report."),
    (P[15], False, "UID number {} was flagged for manual review."),
]
for _aad, _group, _tmpl in _aadhaar_cases:
    _val = grouped(_aad) if _group else _aad
    add("aadhaar", _tmpl.format(_val), [("AADHAAR", _val)])

# ============================== LOCATION =====================================

_locations = [
    "The regional office relocated to Bangalore last month.",
    "She is currently based out of Hyderabad.",
    "The shipment was routed through Chennai port.",
    "His transfer to Pune was approved by HR.",
    "The new warehouse opened in Ahmedabad.",
    "Field operations are managed from Kolkata.",
    "The client's headquarters are in Gurgaon.",
    "The audit team travelled to Kochi for the site visit.",
]
_location_values = ["Bangalore", "Hyderabad", "Chennai", "Pune", "Ahmedabad", "Kolkata", "Gurgaon", "Kochi"]
for _text, _val in zip(_locations, _location_values):
    add("location", _text, [("LOCATION", _val)])

# ============================== MIXED multi-entity ===========================

add(
    "mixed",
    "Contact Priya Sharma at priya.sharma@examplebank.com or +91 98765 43210 regarding the KYC update.",
    [("PERSON", "Priya Sharma"), ("EMAIL", "priya.sharma@examplebank.com"), ("PHONE", "+91 98765 43210")],
)
add(
    "mixed",
    f"Rahul Verma (PAN {PAN['P']}) relocated to Bangalore last week.",
    [("PERSON", "Rahul Verma"), ("PAN", PAN["P"]), ("LOCATION", "Bangalore")],
)
add(
    "mixed",
    f"Ayesha Siddiqui's Aadhaar {grouped(P[0])} and phone 9988776655 were verified together.",
    [("PERSON", "Ayesha Siddiqui"), ("AADHAAR", grouped(P[0])), ("PHONE", "9988776655")],
)
add(
    "mixed",
    "Please forward the invoice to billing@finance.acmeindia.net and cc rahul.verma@examplecorp.com.",
    [("EMAIL", "billing@finance.acmeindia.net"), ("EMAIL", "rahul.verma@examplecorp.com")],
)
add(
    "mixed",
    f"The government PAN {PAN['G']} is linked to an office in Chennai.",
    [("PAN", PAN["G"]), ("LOCATION", "Chennai")],
)
add(
    "mixed",
    "Karthik Iyer, reachable at +91-7012345678, confirmed the Hyderabad site visit.",
    [("PERSON", "Karthik Iyer"), ("PHONE", "+91-7012345678"), ("LOCATION", "Hyderabad")],
)
add(
    "mixed",
    f"Maria Fernandes updated her Aadhaar {P[1]} after moving to Kochi.",
    [("PERSON", "Maria Fernandes"), ("AADHAAR", P[1]), ("LOCATION", "Kochi")],
)
add(
    "mixed",
    f"Gurpreet Singh's PAN {PAN['B']} and phone 9123456780 are both on file.",
    [("PERSON", "Gurpreet Singh"), ("PAN", PAN["B"]), ("PHONE", "9123456780")],
)
add(
    "mixed",
    f"Send the offer letter to happy.singh@examplecorp.in; his Aadhaar is {P[2]}.",
    [("EMAIL", "happy.singh@examplecorp.in"), ("AADHAAR", P[2])],
)
add(
    "mixed",
    "Sneha Mishra (sneha.mishra@corporate-group.org) is based in Gurgaon.",
    [("PERSON", "Sneha Mishra"), ("EMAIL", "sneha.mishra@corporate-group.org"), ("LOCATION", "Gurgaon")],
)
add(
    "mixed",
    f"The vendor contract lists Arjun Reddy as the signatory, PAN {PAN['F']}, based in Pune.",
    [("PERSON", "Arjun Reddy"), ("PAN", PAN["F"]), ("LOCATION", "Pune")],
)
add(
    "mixed",
    "Two numbers on file for Thomas Kurian: +91 90123 45678 and 08012345671.",
    [("PERSON", "Thomas Kurian"), ("PHONE", "+91 90123 45678"), ("PHONE", "08012345671")],
)
add(
    "mixed",
    f"Jaspreet Bhatia's Aadhaar {P[3]} was linked to phone 9345671234 and email jaspreet.b@examplemail.com.",
    [("PERSON", "Jaspreet Bhatia"), ("AADHAAR", P[3]), ("PHONE", "9345671234"), ("EMAIL", "jaspreet.b@examplemail.com")],
)
add(
    "mixed",
    f"Divya Chandrasekaran, PAN {PAN['T']}, relocated from Chennai to Ahmedabad.",
    [("PERSON", "Divya Chandrasekaran"), ("PAN", PAN["T"]), ("LOCATION", "Chennai"), ("LOCATION", "Ahmedabad")],
)
add(
    "mixed",
    f"Escalate to legal.team@corporate-group.org; the applicant's PAN is {PAN['A']}.",
    [("EMAIL", "legal.team@corporate-group.org"), ("PAN", PAN["A"])],
)
add(
    "mixed",
    "Aamir Hussain confirmed his new number +91-8890012345 after moving to Kolkata.",
    [("PERSON", "Aamir Hussain"), ("PHONE", "+91-8890012345"), ("LOCATION", "Kolkata")],
)

# ============================== NEGATIVE — no PII at all =====================

_negatives = [
    "The quarterly board meeting has been rescheduled to next Thursday.",
    "All employees must complete the annual compliance refresher by year end.",
    "The server migration is expected to take approximately six hours.",
    "Please review the attached policy document before the next sync.",
    "The marketing campaign exceeded its engagement targets this quarter.",
    "Office hours during the festive season will be reduced by two hours daily.",
    "The new expense reimbursement policy takes effect next month.",
    "Inventory levels are being reconciled ahead of the year-end audit.",
    "The product roadmap was revised after stakeholder feedback.",
    "Training sessions on the updated software will run throughout the week.",
    "The vendor renewal process now requires additional documentation.",
    "Budget approvals for Q3 are pending finance committee review.",
    "The helpdesk reported a spike in password reset requests.",
    "System maintenance is scheduled for the coming weekend.",
]
for _text in _negatives:
    add("negative_no_pii", _text, [])

# ============================== NEAR-MISS negatives ===========================
# Digit/letter sequences shaped like PII that must NOT be labeled as gold
# entities. Checksum-relevant literals are asserted invalid below rather
# than trusted by eye.

_near_miss_12digit_literal = [
    "Order #487213908475 was dispatched via the regional hub.",
    "Tracking ID 998877665544 shows the package in transit.",
    "Invoice reference 223344556677 was auto-generated by the billing system.",
    "The document was timestamped 202501151234 for audit purposes.",
    "The batch process ID 334455667788 failed to complete.",
    "Serial number 667788990011 was misread by the scanner.",
]
for _text in _near_miss_12digit_literal:
    add("near_miss_no_gold", _text, [])
    # extract the digit run for the checksum assertion below
    _digits = "".join(ch for ch in _text if ch.isdigit())[:12]
    assert len(_digits) == 12
    assert not _verhoeff_validate(_digits), f"accidentally-valid near-miss: {_text}"

add(
    "near_miss_no_gold",
    f"Reference number {corrupt(P[4])} does not match any customer record.",
    [],
)
add(
    "near_miss_no_gold",
    f"The corrupted record {corrupt(P[5])} could not be validated during the audit.",
    [],
)
add("near_miss_no_gold", f"Reference code {INVALID_HOLDER_PANS[0]} was flagged as invalid input.", [])
add("near_miss_no_gold", f"The internal code {INVALID_HOLDER_PANS[1]} appeared in the error log.", [])
add("near_miss_no_gold", "Call the vendor helpline at 5876543210 for support.", [])
add("near_miss_no_gold", "The reference ID 1234567890 was assigned automatically.", [])

# ============================== ORG distractors (no PII) ======================

_orgs = [
    "Meridian Analytics announced a new partnership with Cedar Systems.",
    "Northbridge Consulting was awarded the compliance advisory contract.",
    "Falcon Logistics upgraded its warehouse management software.",
    "Everline Technologies migrated its infrastructure to the cloud.",
    "Sundial Capital reported strong quarterly earnings.",
    "Ashgrove Manufacturing completed its ISO certification renewal.",
]
for _text in _orgs:
    add("org_distractor_no_pii", _text, [])
