
"""Presidio initialization and combined PII detection."""

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .india_recognizers import detect_indian_pii


configuration = {
    "nlp_engine_name": "spacy",
    "models": [
        {
            "lang_code": "en",
            "model_name": "en_core_web_sm",
        }
    ],
}

provider = NlpEngineProvider(nlp_configuration=configuration)
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(
    nlp_engine=nlp_engine,
    supported_languages=["en"],
)


# Conseal currently focuses on Indian PII.
# UK NHS identifiers are outside the supported detection scope.
UNSUPPORTED_ENTITY_TYPES = {
    "UK_NHS",
}


def analyze_text(
    text: str,
    score_threshold: float = 0.91,
) -> list[RecognizerResult]:
    """
    Combine Presidio and India-specific PII detections.

    Results use Presidio's RecognizerResult format so existing
    anonymization code can consume them.
    """

    if not isinstance(text, str) or not text:
        return []

    presidio_results = analyzer.analyze(
        text=text,
        language="en",
        score_threshold=score_threshold,
    )

    # Exclude entity types outside Conseal's supported scope.
    presidio_results = [
        result
        for result in presidio_results
        if result.entity_type not in UNSUPPORTED_ENTITY_TYPES
    ]

    indian_matches = detect_indian_pii(text)

    # Prefer contextually identified UPI over EMAIL_ADDRESS
    # when both recognizers identify the exact same span.
    upi_spans = {
        (match.start, match.end)
        for match in indian_matches
        if match.entity_type == "UPI_ID"
    }

    combined = [
        result
        for result in presidio_results
        if not (
            result.entity_type == "EMAIL_ADDRESS"
            and (result.start, result.end) in upi_spans
        )
    ]

    existing = {
        (
            result.start,
            result.end,
            result.entity_type,
        )
        for result in combined
    }

    for match in indian_matches:
        key = (
            match.start,
            match.end,
            match.entity_type,
        )

        if key in existing:
            continue

        combined.append(
            RecognizerResult(
                entity_type=match.entity_type,
                start=match.start,
                end=match.end,
                score=match.confidence,
            )
        )

        existing.add(key)

    return sorted(
        combined,
        key=lambda result: (
            result.start,
            result.end,
            result.entity_type,
        ),
    )
