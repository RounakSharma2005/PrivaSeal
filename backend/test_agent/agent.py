from google.adk.agents.llm_agent import Agent
from google.adk.models.google_llm import Gemini

root_agent = Agent(
    model=Gemini(model='gemini-2.5-flash'),
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
)
