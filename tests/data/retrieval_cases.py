"""Retrieval-quality evaluation corpus (Task 2 / measuring the project's
central claim: does consistent pseudonymisation preserve retrieval quality
better than naive "redact everything to one fixed placeholder" redaction?).

Design note — this deliberately goes beyond a single-person-per-document
corpus, because that alone wouldn't actually stress-test the claim: if a
document mentions one person twice, BOTH naive redaction (fixed
"[REDACTED]" every time) and consistent pseudonymisation ("PERSON_A" every
time) produce an internally consistent, repeated token — there's nothing
for pseudonymisation to preserve that naive redaction would destroy.

The claim is specifically about distinguishing *different* entities from
each other. So this corpus has two kinds of documents:

- Docs 0-15: one person each, two related facts (the straightforward case,
  included for completeness and as a parity check — not expected to show
  much difference between redaction strategies).
- Docs 16-23: TWO different people each, with the query specifically
  asking about the second-mentioned person's distinct action. Naive
  redaction turns both people into the identical "[REDACTED]" string,
  which should make it harder for an embedding to encode "person who did
  X" as a distinguishable feature of the document, compared to
  "PERSON_A ... PERSON_B" where the two remain lexically distinct within
  the document (though not across documents — see README limitations on
  cross-document pseudonym consistency).

32 distinct full names are used across all 24 documents (no first name or
surname repeated) specifically to avoid a confound where retrieval errors
are caused by two documents mentioning the same real name, rather than by
the redaction strategy under test.

All names are invented; none correspond to a real person.
"""

RETRIEVAL_DOCS = [
    # --- single-person documents (0-15) ---
    "Priya Sharma opened a savings account in Bangalore in March. "
    "Priya Sharma later requested a statement for the same account.",

    "Rahul Verma filed a complaint about a delayed wire transfer. "
    "Rahul Verma escalated the issue the following week.",

    "Karthik Iyer reported a failed UPI payment. "
    "The payment to Karthik Iyer was reversed within two days.",

    "Ayesha Siddiqui requested a replacement debit card. "
    "The new card for Ayesha Siddiqui was dispatched to her registered address.",

    "Gurpreet Singh disputed a credit card charge. "
    "The dispute raised by Gurpreet Singh was resolved in his favour.",

    "Maria Fernandes applied for a personal loan. "
    "The loan for Maria Fernandes was approved after document verification.",

    "Rohan Kurian flagged suspicious activity on his account. "
    "Rohan Kurian's account was temporarily frozen pending review.",

    "Lakshmi Narayanan updated her KYC details. "
    "The updated details for Lakshmi Narayanan were confirmed by the branch.",

    "Imran Qureshi closed his fixed deposit early. "
    "An early-closure penalty was applied to Imran Qureshi's account.",

    "Harpreet Kaur requested a higher credit limit. "
    "Harpreet Kaur's limit was increased after income verification.",

    "Divya Chandrasekaran reported a lost debit card. "
    "Divya Chandrasekaran's card was blocked immediately.",

    "Aamir Hussain set up an auto-debit mandate. "
    "Aamir Hussain's mandate failed due to insufficient balance.",

    "Sneha Mishra requested a tax statement for the financial year. "
    "The statement was emailed to Sneha Mishra's registered address.",

    "Arjun Reddy complained about an ATM that did not dispense cash. "
    "A refund was credited to Arjun Reddy within three business days.",

    "Rose D'Cruz opened a recurring deposit. "
    "Rose D'Cruz increased the monthly instalment after six months.",

    "Jaspreet Bhatia reported unauthorized access to her account. "
    "Two-factor authentication was enabled on Jaspreet Bhatia's account.",

    # --- multi-person documents (16-23): two distinct people, distinct facts ---
    "Venkataraman Subramaniam approved the loan application. "
    "Mohammed Khan, the applicant, received the funds the next day.",

    "Deepa Krishnamurthy escalated the complaint to the regional manager. "
    "The regional manager, Srinivasan Raghavan, resolved it within 48 hours.",

    "Simran Saxena reported the fraud on her account. "
    "Her relationship manager, Meenakshi Sundaram, filed the police report on her behalf.",

    "Sarah Thomas requested the loan restructuring. "
    "Her co-applicant, Paul D'Souza, countersigned the revised agreement.",

    "Anjali Kapoor flagged the discrepancy during the audit. "
    "The branch manager, Vikram Agarwal, corrected the ledger entry.",

    "Neha Chauhan submitted the grievance. "
    "The grievance officer, Manish Tiwari, acknowledged receipt within 24 hours.",

    "Fatima Ansari initiated the wire transfer. "
    "The compliance officer, Zainab Rahman, placed a hold pending verification.",

    "Manjeet Bhatt opened a joint account. "
    "Her co-applicant, Kavya Balasubramanian, was added as a nominee.",
]

RETRIEVAL_QUERIES = [
    # (query, index of the correct document in RETRIEVAL_DOCS)
    ("Who opened a savings account in Bangalore?", 0),
    ("Who filed a complaint about a delayed wire transfer?", 1),
    ("Whose UPI payment was reversed?", 2),
    ("Who requested a replacement debit card?", 3),
    ("Whose credit card dispute was resolved in their favour?", 4),
    ("Who was approved for a personal loan after document verification?", 5),
    ("Whose account was frozen pending review for suspicious activity?", 6),
    ("Who updated their KYC details?", 7),
    ("Who closed a fixed deposit early and paid a penalty?", 8),
    ("Who had their credit limit increased after income verification?", 9),
    ("Who reported a lost debit card that was blocked immediately?", 10),
    ("Whose auto-debit mandate failed due to insufficient balance?", 11),
    ("Who requested a tax statement for the financial year?", 12),
    ("Who complained about an ATM not dispensing cash?", 13),
    ("Who opened a recurring deposit and later increased the instalment?", 14),
    ("Who reported unauthorized access and enabled two-factor authentication?", 15),
    # Multi-person documents: these specifically ask about the SECOND
    # person's action, which is the harder entity-disambiguation case.
    ("Who received loan funds the day after approval?", 16),
    ("Who resolved an escalated complaint within 48 hours?", 17),
    ("Who filed a police report on behalf of a fraud victim?", 18),
    ("Who countersigned a loan restructuring agreement?", 19),
    ("Who corrected a ledger entry after an audit discrepancy?", 20),
    ("Who acknowledged a grievance within 24 hours?", 21),
    ("Who placed a hold on a wire transfer pending verification?", 22),
    ("Who was added as a nominee on a joint account?", 23),
]
