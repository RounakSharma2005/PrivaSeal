from typing import List

from google.adk.agents.llm_agent import Agent
from pydantic import BaseModel, Field


class PrivacyPolicyModel(BaseModel):
    hide: List[str] = Field(default_factory=list)
    keep: List[str] = Field(default_factory=list)
    review: List[str] = Field(default_factory=list)


class PolicyGeneratorResponse(BaseModel):
    purpose: str
    policy: PrivacyPolicyModel


POLICY_GENERATOR_INSTRUCTION = """
You are Conseal's privacy policy generation engine.

Your task is to convert the user's document-processing purpose and
privacy instructions into a structured privacy policy.

You MUST return the exact structured output schema:
{
    "purpose": "string",
    "policy": {
        "hide": ["ENTITY_TYPE"],
        "keep": ["ENTITY_TYPE"],
        "review": ["ENTITY_TYPE"]
    }
}

Use concise, standardized entity labels. Examples include:

PERSON
EMAIL_ADDRESS
PHONE_NUMBER
INDIAN_PHONE
PAN
AADHAAR
UPI_ID
IFSC
ADDRESS
DATE_OF_BIRTH
CREDIT_CARD
BANK_ACCOUNT

RULES:

1. HIDE:
   Place information that should be removed or anonymized here.

2. KEEP:
   Place information that is necessary for the stated purpose and
   explicitly permitted to remain visible here.

3. REVIEW:
   Place information requiring human judgment here.

4. Interpret explicit instructions carefully.
   For example, if the user says "keep IFSC codes visible",
   IFSC MUST appear in the keep list.

5. If the user asks to protect all personal identifiers,
   include relevant personal identifier categories in hide.

6. Do not place the same entity type in multiple categories.

7. Do not invent requirements that contradict the user's instructions.

8. If the purpose is ambiguous, use conservative privacy defaults
   and put context-dependent information in review.

9. Return structured output only. Do not return explanations,
   Markdown, or text outside the schema.

The policy must be actionable by a deterministic PII engine.
"""


root_agent = Agent(
    name="PolicyGenerator",
    model="groq/openai/gpt-oss-120b",
    instruction=POLICY_GENERATOR_INSTRUCTION,
    output_schema=PolicyGeneratorResponse,
)
