
from backend.pii.india_recognizers import detect_indian_pii
from backend.pii.analyzer import analyze_text


# ---------------------------------------------------------
# Existing tests
# ---------------------------------------------------------

def test_indian_phone_candidate_is_detected():
    matches = detect_indian_pii("Contact: +91 98765 43210")

    assert any(
        match.entity_type == "INDIAN_PHONE"
        for match in matches
    )


def test_match_offsets_reference_original_text():
    text = "Customer PAN: ABCDE1234F"

    match = next(
        item
        for item in detect_indian_pii(text)
        if item.entity_type == "PAN"
    )

    assert text[match.start:match.end] == match.value


# ---------------------------------------------------------
# UPI regression tests
# ---------------------------------------------------------

def test_upi_detection_with_trailing_period():
    text = "Send payment to demo@okaxis."

    results = detect_indian_pii(text)

    matches = [
        result
        for result in results
        if result.entity_type == "UPI_ID"
    ]

    assert len(matches) == 1
    assert matches[0].value == "demo@okaxis"


def test_upi_not_duplicated_as_email():
    text = "Send payment to demo@okaxis."

    results = analyze_text(text)

    matching_results = [
        result
        for result in results
        if text[result.start:result.end] == "demo@okaxis"
    ]

    assert len(matching_results) == 1
    assert matching_results[0].entity_type == "UPI_ID"


def test_email_is_not_misclassified_as_upi():
    text = "Contact test.person@example.com"

    results = analyze_text(text)

    assert not any(
        result.entity_type == "UPI_ID"
        for result in results
    )


# ---------------------------------------------------------
# Indian phone regression tests
# ---------------------------------------------------------

def test_indian_phone_detected_with_correct_label():
    text = "Call me at 9876543210."

    results = analyze_text(text)

    matches = [
        result
        for result in results
        if result.entity_type == "INDIAN_PHONE"
    ]

    assert len(matches) == 1
    assert text[matches[0].start:matches[0].end] == "9876543210"


def test_indian_phone_not_classified_as_uk_nhs():
    text = "Call me at 9876543210."

    results = analyze_text(text)

    entity_types = {
        result.entity_type
        for result in results
    }

    assert "UK_NHS" not in entity_types
