from google.adk.agents.llm_agent import Agent
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from google.adk.models.lite_llm import LiteLlm

class EntityExplanation(BaseModel):
    entity_type: str = Field(description="The PII type (e.g. PERSON, EMAIL_ADDRESS)")
    value: str = Field(description="The actual text that was detected")
    explanation: str = Field(description="Why this should be redacted")
    risk_level: str = Field(description="high, medium, or low")
    recommendation: str = Field(description="redact, review, or keep")
    applied_policy_rule: Optional[str] = Field(description="The exact rule text from the Privacy Policy that was used to make this decision")

class MissedEntity(BaseModel):
    entity_type: str = Field(description="The PII type (e.g. PERSON, DATE_OF_BIRTH, ADDRESS)")
    value: str = Field(description="The EXACT text from the original document that should be redacted")
    explanation: str = Field(description="Why this was missed and why it should be redacted")
    risk_level: str = Field(description="high, medium, or low")
    recommendation: str = Field(description="redact, review, or keep")
    applied_policy_rule: Optional[str] = Field(description="The exact rule text from the Privacy Policy that was used to make this decision")

class NonRedactedExplanation(BaseModel):
    value: str = Field(description="The text that was NOT flagged")
    type: str = Field(description="What type of information it is")
    explanation: str = Field(description="Why it was not flagged")
    reason_kept: str = Field(description="Why it is safe to keep")

class PIIExplainerResponse(BaseModel):
    entity_explanations: List[EntityExplanation]
    missed_entities: List[MissedEntity]
    non_redacted_explanations: List[NonRedactedExplanation]
    overall_risk_summary: str = Field(description="A brief overall privacy risk assessment of the document")


PII_EXPLAINER_INSTRUCTION = """
You are a PII (Personally Identifiable Information) explainability assistant for a privacy-first document anonymization tool.

You will receive the original text, a list of PII entities detected by Google Cloud DLP (a deterministic PII detection engine), and a User Privacy Policy (based on their intended purpose).

CRITICAL RULE: The User Privacy Policy is the ABSOLUTE SOURCE OF TRUTH. If the policy explicitly states to "keep" a type of information, you MUST recommend "keep", even if it is normally considered highly sensitive PII. Do not override the user's custom policy under any circumstances.

Your responsibilities:

1. EXPLAIN REDACTIONS & KEEPS: For each detected PII entity, evaluate it against the Privacy Policy. Provide:
   - A clear, human-readable explanation of WHY it should be redacted OR kept, explicitly referencing the policy. If the policy says to keep it, explain that the user explicitly allowed it.
   - A risk level: "high", "medium", or "low" (reflecting the inherent risk, even if kept)
   - A recommendation: "redact" (remove), "review" (user should decide), or "keep" (safe to keep, or explicitly allowed by policy)

2. FIND MISSED PII: Carefully review the ENTIRE original text for any PII that Google Cloud DLP MISSED that SHOULD be redacted according to the Privacy Policy. Do NOT flag missed PII if the policy says to keep it.
   For each missed entity, provide the EXACT text as it appears in the original, its type, and an explanation referencing the policy.

3. EXPLAIN NON-REDACTIONS: Identify notable words or phrases in the text that were NOT flagged as PII (or that the policy explicitly says to Keep), but a user might wonder about. For each, explain WHY it is safe to keep visible, explicitly referencing the policy.

4. CONTEXTUAL ANALYSIS: Consider the document context and the user's purpose.

5. OVERALL RISK SUMMARY: Provide a brief overall privacy risk assessment, noting how well the document aligns with the provided privacy policy.
"""

agent = Agent(
    name="PIIExplainer",
    model="groq/openai/gpt-oss-120b",
    instruction=PII_EXPLAINER_INSTRUCTION,
    output_schema=PIIExplainerResponse,
)

root_agent = agent
