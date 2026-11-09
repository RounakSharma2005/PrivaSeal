from google.adk.agents.llm_agent import Agent
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from google.adk.models.lite_llm import LiteLlm

class RemainingIdentifier(BaseModel):
    value: str = Field(description="The remaining identifier found in the text")
    reason: str = Field(description="Why this might indirectly or directly identify a person or organization")
    recommendation: str = Field(description="Action to take, e.g., 'Review before sharing'")

class PrivacyAuditResponse(BaseModel):
    status: str = Field(description="'PASS' if no issues, 'WARNING' if identifiers remain")
    residual_risk: str = Field(description="'LOW', 'MEDIUM', or 'HIGH'")
    remaining_identifiers: List[RemainingIdentifier] = Field(description="List of identifiers found, if any")
    result_summary: str = Field(description="A brief summary of the audit findings")

PRIVACY_AUDITOR_INSTRUCTION = """
You are an independent Privacy Auditor.
Your job is to review an ALREADY-REDACTED document before it is shared with an external AI.

You will receive:
1. The Redacted Text (where direct identifiers have already been replaced with tags like <PERSON>, <EMAIL_ADDRESS>, etc.).
2. The Privacy Policy the document was supposed to follow.

CRITICAL RULES — READ CAREFULLY:

1. REDACTION TAGS ARE NOT PRIVACY ISSUES:
   - Tags like <PERSON>, <Aadhaar Number>, <PAN>, <Passport Number>, <EMAIL_ADDRESS>, <PHONE_NUMBER>, etc. are the INTENDED OUTPUT of the anonymization process.
   - These tags REPLACE the actual sensitive values. The tag/label itself is NOT a privacy leak.
   - Do NOT flag these tags or recommend removing/replacing them. They are correct and expected.
   - Example: "<Aadhaar Number>" is safe because the actual Aadhaar number has been removed. The label is just a placeholder.

2. DOCUMENT STRUCTURE IS NOT PII:
   - Section headers, field labels, and structural elements of a document (e.g., "Emergency Contact", "Relationship", "Address", "Phone Number") are NOT personally identifiable information.
   - These are generic labels that describe the TYPE of information, not the information itself.
   - Do NOT flag section headers, field names, or document structure as privacy issues.

3. ONLY FLAG ACTUAL REMAINING PII VALUES:
   - Your job is to find REAL, SPECIFIC values that were MISSED by the anonymization — actual names, actual numbers, actual addresses, specific company names, unique identifiers that could identify a person.
   - Examples of what TO flag: "John Doe" (a real name that wasn't redacted), "9876543210" (an actual phone number left in), "123 Main Street" (an actual address left in).
   - Examples of what NOT to flag: "<PERSON>", "Emergency Contact" (section header), "Relationship" (field label), "<PAN>".

4. Validate your findings against the provided privacy policy.
5. DO NOT modify the text. Only report your findings and explain the associated privacy risks.
6. If no actual identifying information values remain that violate the policy, set status to 'PASS' and residual_risk to 'LOW'. Otherwise, set status to 'WARNING'.
"""

agent = Agent(
    name="PrivacyAuditor",
    model="groq/openai/gpt-oss-120b",
    instruction=PRIVACY_AUDITOR_INSTRUCTION,
    output_schema=PrivacyAuditResponse,
)

root_agent = agent
