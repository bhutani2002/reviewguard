import os
import json

# Detect mock mode
MOCK_MODE = os.getenv("REVIEWGUARD_MOCK", "false").lower() == "true"

def load_mock_fixture(key: str) -> any:
    """Load mock data from the active scenario fixture file."""
    scenario_path = os.getenv(
        "REVIEWGUARD_MOCK_SCENARIO",
        "evals/datasets/partial_pr.json"
    )
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    return scenario["mock_fixtures"][key]
