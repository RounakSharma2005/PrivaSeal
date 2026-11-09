from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

session_service = InMemorySessionService()

_runners: dict[str, Runner] = {}

def _get_agent(app_name: str):
    """Lazily import and return the appropriate agent for the given app_name."""
    if app_name == "pii_explainer":
        try:
            from ...agents.pii_explainer.agent import root_agent
        except ImportError:
            from agents.pii_explainer.agent import root_agent
        return root_agent
    elif app_name == "policy_generator":
        try:
            from ...agents.policy_generator.agent import root_agent
        except ImportError:
            from agents.policy_generator.agent import root_agent
        return root_agent
    elif app_name == "privacy_auditor":
        try:
            from ...agents.privacy_auditor.agent import root_agent
        except ImportError:
            from agents.privacy_auditor.agent import root_agent
        return root_agent
    else:
        raise ValueError(f"Unknown agent: {app_name}")

def get_runner(app_name: str) -> Runner:
    """Get or create a Runner for the given app_name."""
    if app_name not in _runners:
        agent = _get_agent(app_name)
        _runners[app_name] = Runner(
            agent=agent,
            app_name=app_name,
            session_service=session_service,
        )
    return _runners[app_name]
