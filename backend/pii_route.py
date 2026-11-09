
"""Conseal API routes for PII detection, policy, audit and PDF processing."""

from __future__ import annotations

import io
import json
import os
import re
import uuid
from typing import Any, List, Optional

import pymupdf

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Form,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from google.genai import types
from presidio_analyzer import RecognizerResult
import zipfile
try:
    from .pii.evidence_report import build_evidence_report
except ImportError:
    from pii.evidence_report import build_evidence_report

async def validate_pdf_upload(upload: UploadFile) -> bytes:
    """
    Validate an uploaded PDF file.

    Checks:
    - File extension
    - Empty uploads
    - PDF magic signature
    - Maximum upload size

    Returns:
        Validated PDF content as bytes.
    """

    # 1. Validate file extension
    filename = upload.filename or ""

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Only PDF files are allowed.",
        )

    # 2. Read uploaded content
    content = await upload.read()

    # 3. Reject empty files
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded PDF file is empty.",
        )

    # 4. Validate PDF signature
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail="Invalid PDF file signature.",
        )

    # 5. Enforce 15 MB upload limit
    max_size = 15 * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail="PDF file exceeds the maximum allowed size of 15 MB.",
        )

    return content

try:
    from .pii.analyzer import analyze_text
    from .pii.anonymizer import anonymizer
    from .pii.pdf_ocr import extract_pdf_text
    from .pii.pdf_verifier import verify_redacted_pdf
    from .pii.pdf_sanitizer import sanitize_pdf
    from .common.config.adk import get_runner

except ImportError:
    from pii.analyzer import analyze_text
    from pii.anonymizer import anonymizer
    from pii.pdf_ocr import extract_pdf_text
    from pii.pdf_verifier import verify_redacted_pdf
    from pii.pdf_sanitizer import sanitize_pdf
    from common.config.adk import get_runner


router = APIRouter()


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

# External LLM review is disabled by default.
# Enable explicitly with ENABLE_LLM_REVIEW=true.
ENABLE_LLM_REVIEW = (
    os.getenv("ENABLE_LLM_REVIEW", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)


# -------------------------------------------------------------------
# Request and response models
# -------------------------------------------------------------------

class PrivacyPolicy(BaseModel):
    hide: List[str] = Field(default_factory=list)
    keep: List[str] = Field(default_factory=list)
    review: List[str] = Field(default_factory=list)


class PolicyRequest(BaseModel):
    purpose: str


class PolicyResponse(BaseModel):
    purpose: str
    policy: PrivacyPolicy


class RefinePolicyRequest(BaseModel):
    current_policy: PrivacyPolicy
    user_prompt: str


class PIIRequest(BaseModel):
    text: str
    purpose: Optional[str] = None
    policy: Optional[PrivacyPolicy] = None


class PIIEntity(BaseModel):
    type: str
    start: int
    end: int
    score: float
    value: str
    explanation: str
    risk_level: str
    recommendation: str
    detected_by: str
    applied_policy_rule: Optional[str] = None


# -------------------------------------------------------------------
# Deterministic privacy policy application
# -------------------------------------------------------------------

POLICY_ENTITY_ALIASES = {
    "NAME": "PERSON",
    "NAMES": "PERSON",
    "PERSON_NAME": "PERSON",
    "PERSON_NAMES": "PERSON",
    "EMAIL": "EMAIL_ADDRESS",
    "EMAILS": "EMAIL_ADDRESS",
    "EMAIL_ADDRESSES": "EMAIL_ADDRESS",
    "PHONE": "PHONE_NUMBER",
    "PHONES": "PHONE_NUMBER",
    "PHONE_NUMBERS": "PHONE_NUMBER",
    "INDIAN_PHONE_NUMBER": "INDIAN_PHONE",
    "AADHAAR_NUMBER": "AADHAAR",
    "AADHAAR_NUMBERS": "AADHAAR",
    "PAN_NUMBER": "PAN",
    "UPI": "UPI_ID",
    "UPI_IDS": "UPI_ID",
    "IFSC_CODE": "IFSC",
    "IFSC_CODES": "IFSC",
    "ADDRESSES": "ADDRESS",
    "DOB": "DATE_OF_BIRTH",
    "CREDIT_CARD_NUMBER": "CREDIT_CARD",
    "BANK_ACCOUNT_NUMBER": "BANK_ACCOUNT",
}


def _canonical_policy_entity(value: str) -> str:
    """Normalize policy labels and detector entity names."""
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper()).strip("_")
    return POLICY_ENTITY_ALIASES.get(normalized, normalized)


def _get_policy_action(
    entity_type: str,
    policy: Optional[dict],
) -> tuple[str, Optional[str]]:
    """Resolve an entity against hide/keep/review policy lists.

    Conflicts are resolved conservatively: hide > review > keep.
    Entities not mentioned in a supplied policy retain default redaction.
    With no policy, the existing default redaction behavior is preserved.
    """
    if policy is None:
        return "redact", None

    if hasattr(policy, "model_dump"):
        policy = policy.model_dump()
    if not isinstance(policy, dict):
        raise ValueError("Privacy policy must be a JSON object.")

    categories = {}
    for category in ("hide", "keep", "review"):
        values = policy.get(category, [])
        if not isinstance(values, list):
            raise ValueError(f"Policy '{category}' must be a list.")
        categories[category] = {
            _canonical_policy_entity(item)
            for item in values
            if isinstance(item, str) and item.strip()
        }

    canonical_type = _canonical_policy_entity(entity_type)
    if canonical_type in categories["hide"]:
        return "redact", "hide"
    if canonical_type in categories["review"]:
        return "review", "review"
    if canonical_type in categories["keep"]:
        return "keep", "keep"
    return "redact", "default_redact"


class NonRedactedItem(BaseModel):
    value: str
    type: str
    explanation: str
    reason_kept: str


class PIIResponse(BaseModel):
    original_text: str
    anonymized_text: str
    entities: List[PIIEntity]
    non_redacted: List[NonRedactedItem]
    overall_risk_summary: str


class AuditRequest(BaseModel):
    redacted_text: str
    policy: Optional[PrivacyPolicy] = None


class RemainingIdentifier(BaseModel):
    value: str
    reason: str
    recommendation: str


class AuditResponse(BaseModel):
    status: str
    residual_risk: str
    remaining_identifiers: List[RemainingIdentifier]
    result_summary: str


# -------------------------------------------------------------------
# LLM helpers
# -------------------------------------------------------------------

async def _run_agent_json(
    agent_name: str,
    prompt: str,
    fallback: dict,
) -> dict:
    """Run an ADK agent and safely parse its JSON response."""

    runner = get_runner(agent_name)

    session = await runner.session_service.create_session(
        app_name=agent_name,
        user_id="anonymous",
        session_id=str(uuid.uuid4()),
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=prompt)],
    )

    response_text = ""

    async for event in runner.run_async(
        user_id="anonymous",
        session_id=session.id,
        new_message=message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    try:
        cleaned = response_text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [
                line
                for line in lines
                if not line.strip().startswith("```")
            ]
            cleaned = "\n".join(lines)

        parsed = json.loads(cleaned)

        return parsed if isinstance(parsed, dict) else fallback

    except (json.JSONDecodeError, ValueError):
        return fallback


async def _generate_policy(purpose: str) -> dict:
    """Generate a structured, actionable privacy policy."""
    prompt = (
        "Create a privacy policy for the following document-processing purpose.\n"
        f"Purpose and user instructions: {purpose}\n\n"
        "Return a JSON object with exactly these keys: purpose and policy.\n"
        "policy must contain three lists: hide, keep, review.\n"
        "Use canonical entity labels where applicable: PERSON, EMAIL_ADDRESS, "
        "PHONE_NUMBER, INDIAN_PHONE, PAN, AADHAAR, UPI_ID, IFSC, ADDRESS, "
        "DATE_OF_BIRTH, CREDIT_CARD, BANK_ACCOUNT.\n"
        "Follow explicit instructions. If the user says keep IFSC codes, put IFSC "
        "in keep. If the user says redact names, put PERSON in hide. Do not put "
        "the same entity type in multiple lists. Put ambiguous/context-dependent "
        "items in review. Return structured JSON only."
    )
    fallback = {
        "purpose": purpose,
        "policy": {"hide": [], "keep": [], "review": []},
    }
    result = await _run_agent_json("policy_generator", prompt, fallback)
    if not isinstance(result.get("policy"), dict):
        return fallback
    for category in ("hide", "keep", "review"):
        values = result["policy"].get(category, [])
        if not isinstance(values, list):
            result["policy"][category] = []
        else:
            result["policy"][category] = [
                str(value).strip() for value in values
                if isinstance(value, str) and value.strip()
            ]
    result["purpose"] = str(result.get("purpose") or purpose)
    return result


async def _refine_policy(
    current_policy: dict,
    user_prompt: str,
) -> dict:

    prompt = (
        f"Here is the current policy:\n"
        f"{json.dumps(current_policy, indent=2)}\n\n"
        f"The user wants to modify it based on this instruction:\n"
        f"{user_prompt}\n\n"
        "Generate the updated policy."
    )

    return await _run_agent_json(
        "policy_generator",
        prompt,
        {
            "purpose": "Refined Policy",
            "policy": current_policy,
        },
    )


async def _run_privacy_audit(
    redacted_text: str,
    policy: Optional[dict] = None,
) -> dict:
    """Run an explicitly requested LLM privacy audit."""

    policy_str = ""

    if policy:
        policy_str = (
            "Privacy Policy:\n"
            f"{json.dumps(policy, indent=2)}\n\n"
        )

    prompt = (
        "Analyze the following REDACTED text.\n\n"
        f"{policy_str}"
        f"Redacted Text:\n{redacted_text}\n"
    )

    fallback = {
        "status": "WARNING",
        "residual_risk": "HIGH",
        "remaining_identifiers": [],
        "result_summary": "Failed to generate audit report.",
    }

    return await _run_agent_json(
        "privacy_auditor",
        prompt,
        fallback,
    )


async def _get_llm_explanations(
    text: str,
    detected_entities: list,
    purpose: Optional[str] = None,
    policy: Optional[dict] = None,
) -> dict:
    """Ask the LLM to explain detections and identify possible misses."""

    policy_str = ""

    if purpose or policy:
        policy_str = (
            f"Intended Purpose: {purpose or 'Not specified'}\n"
            "User Privacy Policy:\n"
            f"{json.dumps(policy or {}, indent=2)}\n\n"
        )

    prompt = (
        "Analyze the following text and PII detection results.\n\n"
        f"{policy_str}"
        f"Original Text:\n{text}\n\n"
        "Detected PII Entities:\n"
        f"{json.dumps(detected_entities, indent=2)}\n\n"
        "Provide explanations for each detected entity and identify "
        "notable non-redacted items."
    )

    fallback = {
        "entity_explanations": [],
        "missed_entities": [],
        "non_redacted_explanations": [],
        "overall_risk_summary": (
            "Deterministic analysis completed. "
            "Optional LLM review is disabled."
        ),
    }

    return await _run_agent_json(
        "pii_explainer",
        prompt,
        fallback,
    )


# -------------------------------------------------------------------
# Deterministic PII analysis pipeline
# -------------------------------------------------------------------

async def _run_pii_pipeline(
    text: str,
    purpose: Optional[str] = None,
    policy: Optional[dict] = None,
) -> dict:
    """Run deterministic detection followed by optional LLM review."""

    # Layer 1: deterministic detection.
    results = analyze_text(
        text,
        score_threshold=0.91,
    )

    detected_entities = [
        {
            "type": result.entity_type,
            "value": text[result.start:result.end],
            "start": result.start,
            "end": result.end,
            "score": result.score,
        }
        for result in results
    ]

    # Layer 2: optional external LLM review.
    if ENABLE_LLM_REVIEW:
        llm_result = await _get_llm_explanations(
            text,
            detected_entities,
            purpose,
            policy,
        )
    else:
        llm_result = {
            "entity_explanations": [],
            "missed_entities": [],
            "non_redacted_explanations": [],
            "overall_risk_summary": (
                "Deterministic PII analysis completed. "
                "External LLM review is disabled."
            ),
        }

    llm_entity_map = {}

    for entity in llm_result.get("entity_explanations", []):
        key = (
            entity.get("entity_type", ""),
            entity.get("value", ""),
        )
        llm_entity_map[key] = entity

    # LLM-suggested missed entities are used only when enabled.
    missed_results = []

    for missed in llm_result.get("missed_entities", []):
        value = missed.get("value", "")
        entity_type = missed.get("entity_type", "UNKNOWN")

        if not value:
            continue

        start_idx = 0

        while True:
            position = text.find(value, start_idx)

            if position == -1:
                break

            end_position = position + len(value)

            already_covered = any(
                result.start <= position
                and result.end >= end_position
                for result in results
            )

            if not already_covered:
                missed_results.append(
                    RecognizerResult(
                        entity_type=entity_type,
                        start=position,
                        end=end_position,
                        score=0.85,
                    )
                )

            start_idx = end_position

    all_results = list(results) + missed_results

    entities = []

    for result in results:
        value = text[result.start:result.end]

        llm_info = llm_entity_map.get(
            (result.entity_type, value),
            {},
        )

        entities.append(
            PIIEntity(
                type=result.entity_type,
                start=result.start,
                end=result.end,
                score=result.score,
                value=value,
                explanation=llm_info.get(
                    "explanation",
                    (
                        f"Detected as {result.entity_type} "
                        f"with {result.score:.0%} confidence."
                    ),
                ),
                risk_level=llm_info.get("risk_level", "medium"),
                recommendation=llm_info.get(
                    "recommendation",
                    "redact",
                ),
                detected_by="presidio",
                applied_policy_rule=llm_info.get(
                    "applied_policy_rule",
                ),
            )
        )

    missed_entity_map = {}

    for missed in llm_result.get("missed_entities", []):
        key = (
            missed.get("entity_type", ""),
            missed.get("value", ""),
        )
        missed_entity_map[key] = missed

    for result in missed_results:
        value = text[result.start:result.end]

        llm_info = missed_entity_map.get(
            (result.entity_type, value),
            {},
        )

        entities.append(
            PIIEntity(
                type=result.entity_type,
                start=result.start,
                end=result.end,
                score=result.score,
                value=value,
                explanation=llm_info.get(
                    "explanation",
                    f"Possible LLM-detected {result.entity_type}.",
                ),
                risk_level=llm_info.get("risk_level", "high"),
                recommendation=llm_info.get(
                    "recommendation",
                    "redact",
                ),
                detected_by="llm",
                applied_policy_rule=llm_info.get(
                    "applied_policy_rule",
                ),
            )
        )

    # Apply the policy to every detected entity, independently of optional LLM review.
    # Hide wins over review, and review wins over keep if conflicting lists are supplied.
    redaction_keys = set()
    for entity in entities:
        action, policy_rule = _get_policy_action(entity.type, policy)
        entity.recommendation = action
        entity.applied_policy_rule = policy_rule
        if action == "redact":
            redaction_keys.add((entity.type, entity.start, entity.end))

    non_redacted = []

    for item in llm_result.get(
        "non_redacted_explanations",
        [],
    ):
        non_redacted.append(
            NonRedactedItem(
                value=item.get("value", ""),
                type=item.get("type", "UNKNOWN"),
                explanation=item.get("explanation", ""),
                reason_kept=item.get("reason_kept", ""),
            )
        )

    for entity in entities:
        if entity.recommendation == "keep":
            non_redacted.append(
                NonRedactedItem(
                    value=entity.value,
                    type=entity.type,
                    explanation="Retained according to the privacy policy.",
                    reason_kept="Matched the policy keep category.",
                )
            )
        elif entity.recommendation == "review":
            non_redacted.append(
                NonRedactedItem(
                    value=entity.value,
                    type=entity.type,
                    explanation="This entity requires human review.",
                    reason_kept="Matched the policy review category; it was not automatically redacted.",
                )
            )

    # Only redact results whose corresponding entity decision is 'redact'.
    redaction_results = [
        result for result in all_results
        if (result.entity_type, result.start, result.end) in redaction_keys
    ]
    safe_text = anonymizer.anonymize(
        text=text,
        analyzer_results=redaction_results,
    )

    return {
        "original_text": text,
        "anonymized_text": safe_text.text,
        "entities": entities,
        "non_redacted": non_redacted,
        "overall_risk_summary": llm_result.get(
            "overall_risk_summary",
            "Automated analysis completed; review results.",
        ),
    }


# -------------------------------------------------------------------
# OCR redaction helpers
# -------------------------------------------------------------------

def _normalise_ocr_token(value: str) -> str:
    """Normalize an OCR token for matching."""

    return re.sub(
        r"[^a-z0-9]",
        "",
        value.casefold(),
    )


def _find_ocr_redaction_rectangles(
    page_words: list[dict[str, Any]],
    target: str,
) -> list[pymupdf.Rect]:
    """Find OCR word boxes matching a supplied value or phrase."""

    target_tokens = [
        _normalise_ocr_token(token)
        for token in target.split()
    ]

    target_tokens = [
        token for token in target_tokens if token
    ]

    if not target_tokens:
        return []

    normalized_words = [
        _normalise_ocr_token(word.get("text", ""))
        for word in page_words
    ]

    rectangles = []
    target_length = len(target_tokens)

    for index in range(
        len(normalized_words) - target_length + 1
    ):
        candidate = normalized_words[
            index:index + target_length
        ]

        if candidate != target_tokens:
            continue

        for word in page_words[
            index:index + target_length
        ]:
            bbox = word.get("bbox")

            if not bbox or len(bbox) != 4:
                continue

            rect = pymupdf.Rect(bbox)

            if not rect.is_empty and not rect.is_infinite:
                rectangles.append(rect)

    return rectangles


# -------------------------------------------------------------------
# API routes
# -------------------------------------------------------------------

@router.post("/audit", response_model=AuditResponse)
async def run_audit(request: AuditRequest):
    """Run an explicitly requested LLM privacy audit."""

    policy_dict = (
        request.policy.model_dump()
        if request.policy
        else None
    )

    result = await _run_privacy_audit(
        request.redacted_text,
        policy_dict,
    )

    return AuditResponse(**result)


@router.post("/policy", response_model=PolicyResponse)
async def generate_policy(request: PolicyRequest):
    """Generate a privacy policy from the intended purpose."""

    result = await _generate_policy(request.purpose)

    return PolicyResponse(**result)


@router.post(
    "/policy/refine",
    response_model=PolicyResponse,
)
async def refine_policy(request: RefinePolicyRequest):
    """Refine a privacy policy using user instructions."""

    policy_dict = request.current_policy.model_dump()

    result = await _refine_policy(
        policy_dict,
        request.user_prompt,
    )

    return PolicyResponse(**result)


@router.post("/anonymize", response_model=PIIResponse)
async def anonymize_text(request: PIIRequest):
    """Analyze and anonymize text."""

    policy_dict = (
        request.policy.model_dump()
        if request.policy
        else None
    )

    result = await _run_pii_pipeline(
        request.text,
        request.purpose,
        policy_dict,
    )

    return PIIResponse(**result)


@router.post("/upload", response_model=PIIResponse)
async def upload_document(
    file: UploadFile = File(...),
    purpose: Optional[str] = Form(None),
    policy_json: Optional[str] = Form(None),
):
    """Extract PDF or UTF-8 text and analyze its contents."""

    policy_dict = None

    if policy_json:
        try:
            policy_dict = json.loads(policy_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid policy JSON format.",
            ) from exc

        if not isinstance(policy_dict, dict):
            raise HTTPException(
                status_code=400,
                detail="Policy JSON must be a JSON object.",
            )
        for category in ("hide", "keep", "review"):
            if category in policy_dict and not isinstance(policy_dict[category], list):
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{category}' must be a JSON list.",
                )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    is_pdf = (
        file.content_type == "application/pdf"
        or (file.filename or "").lower().endswith(".pdf")
    )

    if is_pdf:
        try:
            extraction = extract_pdf_text(content)
            text = extraction["text"]

            if not text.strip():
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "No text could be extracted from this PDF. "
                        "The document may be blank or OCR may not "
                        "have recognized its contents."
                    ),
                )

        except HTTPException:
            raise

        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=422,
                detail=f"PDF text extraction failed: {exc}",
            ) from exc

    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="File is not valid UTF-8 text.",
            ) from exc

    result = await _run_pii_pipeline(
        text,
        purpose,
        policy_dict,
    )

    return PIIResponse(**result)


@router.post("/export")
async def export_redacted(request: PIIRequest):
    """Export redacted text using deterministic detection."""

    results = analyze_text(
        request.text,
        score_threshold=0.91,
    )

    safe_text = anonymizer.anonymize(
        text=request.text,
        analyzer_results=results,
    )

    buffer = io.BytesIO(
        safe_text.text.encode("utf-8"),
    )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/plain",
        headers={
            "Content-Disposition": (
                'attachment; filename="redacted_document.txt"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.post("/export_pdf")
async def export_redacted_pdf(
    file: UploadFile = File(...),
    redactions_json: str = Form(...),
    include_evidence: bool = Form(False),
):
    """Redact, sanitize and verify a PDF before returning it."""

    try:
        redactions = json.loads(redactions_json)

    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid redactions JSON format.",
        ) from exc

    if not isinstance(redactions, list):
        raise HTTPException(
            status_code=400,
            detail="Redactions must be a JSON list.",
        )

   # Validate extension, signature, empty content and maximum size.
    content = await validate_pdf_upload(file)
    for item in redactions:
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=400,
                detail="Each redaction must be a JSON object.",
            )

        action = item.get("action", "redact")

        if action not in {"redact", "anonymize", "keep"}:
            raise HTTPException(
                status_code=400,
                detail="Unsupported redaction action.",
            )

        if action != "keep":
            value = item.get("value")

            if not isinstance(value, str) or not value.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Each redaction must include a non-empty value.",
                )

    

    
    # Extract native text and OCR word coordinates before modification.
    try:
        extraction = extract_pdf_text(content)

    except Exception as exc:
     import traceback
     traceback.print_exc()

     raise HTTPException(
        status_code=422,
        detail=(
            "Could not extract PDF text for redaction: "
            f"{type(exc).__name__}: {str(exc)}"
        ),
    ) from exc

    sensitive_values = [
        item["value"].strip()
        for item in redactions
        if item.get("action", "redact") != "keep"
        and isinstance(item.get("value"), str)
        and item["value"].strip()
    ]

    try:
        with pymupdf.open(
            stream=content,
            filetype="pdf",
        ) as doc:

            if len(doc) != extraction["page_count"]:
                raise ValueError(
                    "PDF page count changed during extraction."
                )

            for page_index, page in enumerate(doc):
                page_info = extraction["pages"][page_index]
                ocr_words = page_info["words"]

                rectangles_to_redact = []

                for item in redactions:
                    value = item.get("value")
                    action = item.get("action", "redact")
                    entity_type = str(
                        item.get("type", "REDACTED")
                    )

                    if action == "keep":
                        continue

                    if not isinstance(value, str) or not value.strip():
                        continue

                    value = value.strip()

                    # Native searchable text.
                    for rect in page.search_for(value):
                        rectangles_to_redact.append(
                            (rect, action, entity_type)
                        )

                    # Scanned image text.
                    if page_info["source"] == "ocr":
                        ocr_rectangles = (
                            _find_ocr_redaction_rectangles(
                                ocr_words,
                                value,
                            )
                        )

                        for rect in ocr_rectangles:
                            already_covered = any(
                                rect.intersects(existing_rect)
                                for (
                                    existing_rect,
                                    _,
                                    _,
                                ) in rectangles_to_redact
                            )

                            if not already_covered:
                                rectangles_to_redact.append(
                                    (rect, action, entity_type)
                                )

                # Add actual PDF redaction annotations.
                for rect, action, entity_type in rectangles_to_redact:
                    if action == "anonymize":
                        page.add_redact_annot(
                            rect,
                            text=f"<{entity_type}>",
                            fill=(1, 1, 1),
                            text_color=(0, 0, 0),
                        )

                    else:
                        page.add_redact_annot(
                            rect,
                            fill=(0, 0, 0),
                        )

                # Apply redactions to text and overlapping image pixels.
                page.apply_redactions(images=2)

            # Clear standard metadata before saving.
            doc.set_metadata({
                "title": "",
                "author": "",
                "subject": "",
                "keywords": "",
                "creator": "",
                "producer": "",
                "creationDate": "",
                "modDate": "",
                "trapped": "",
            })

            try:
                doc.del_xml_metadata()
            except (AttributeError, RuntimeError):
                pass

            buffer = io.BytesIO()

            doc.save(
                buffer,
                garbage=4,
                deflate=True,
            )

            redacted_pdf_bytes = buffer.getvalue()

        # Sanitize the saved PDF.
        sanitized_pdf_bytes, sanitization_summary = sanitize_pdf(
            redacted_pdf_bytes
        )

        # Verify the final sanitized bytes, not the original document.
        verification = verify_redacted_pdf(
            sanitized_pdf_bytes,
            sensitive_values,
        )

        if not verification["verified"]:
            failed_checks = [
                name
                for name, check in verification["checks"].items()
                if not check.get("passed", False)
            ]

            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "The exported PDF did not pass all "
                        "post-export verification checks."
                    ),
                    "failed_checks": failed_checks,
                    "finding_count": len(verification["findings"]),
                },
            )

        # Assign filename BEFORE using it in ZIP export.
        filename = (
            file.filename or "document.pdf"
        ).replace("\r", "").replace("\n", "").replace('"', "")

        # Generate evidence report.
        evidence_entities = [
            {
                "type": str(item.get("type", "UNKNOWN")),
                "recommendation": str(
                    item.get("action", "redact")
                ).lower(),
            }
            for item in redactions
        ]

        evidence_report = build_evidence_report(
            document_type="PDF",
            purpose="document_redaction",
            entities=evidence_entities,
            sanitization_summary=sanitization_summary,
            verification=verification,
        )

        if include_evidence:
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(
                zip_buffer,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr(
                    f"redacted_{filename}",
                    sanitized_pdf_bytes,
                )

                archive.writestr(
                    "privacy_evidence_report.json",
                    json.dumps(
                        evidence_report,
                        indent=2,
                        ensure_ascii=False,
                    ),
                )

            zip_buffer.seek(0)

            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": (
                        'attachment; filename="privaseal_export.zip"'
                    ),
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                    "X-Redaction-Verified": "true",
                },
            )

        output = io.BytesIO(sanitized_pdf_bytes)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="redacted_{filename}"'
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Redaction-Verified": "true",
            },
        )
        output = io.BytesIO(sanitized_pdf_bytes)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="redacted_{filename}"'
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Redaction-Verified": "true",
            },
        )

    except HTTPException:
        raise

    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"PDF processing failed: {type(exc).__name__}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PDF redaction failed: {type(exc).__name__}",
        ) from exc
