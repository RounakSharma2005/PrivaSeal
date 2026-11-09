
from backend.pii.analyzer import analyze_text


def test_custom_pan_detection_flows_through_combined_analyzer():
    text = "Customer PAN: ABCDE1234F"

    results = analyze_text(text)

    assert any(
        result.entity_type == "PAN"
        and text[result.start:result.end] == "ABCDE1234F"
        for result in results
    )


def test_custom_ifsc_detection_flows_through_combined_analyzer():
    text = "Bank IFSC: HDFC0001234"

    results = analyze_text(text)

    assert any(
        result.entity_type == "IFSC"
        and text[result.start:result.end] == "HDFC0001234"
        for result in results
    )


def test_combined_analyzer_returns_empty_for_empty_text():
    assert analyze_text("") == []
