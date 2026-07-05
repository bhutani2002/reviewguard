.PHONY: install lint info playground run eval-traces eval-grade eval deploy

# Setup
install:
	uv sync
	@echo "✅  Dependencies installed"

# Lint via agents-cli
lint:
	agents-cli lint
	@echo "✅  Lint passed"

# Show installed agent info and skills
info:
	agents-cli info
	@echo ""
	@echo "Custom skills:"
	agents-cli skills list

# ─────────────────────────────────────────────────────────────────────────────
# PLAYGROUND — local interactive testing
# This is how you verify nodes are working during development.
# Run this on your machine while building. NOT for judges — judges see GitHub.
# ─────────────────────────────────────────────────────────────────────────────
playground:
	@echo "Starting ReviewGuard playground..."
	@echo "Requires: GEMINI_API_KEY and GITHUB_TOKEN set in environment"
	@echo ""
	agents-cli playground --port 8090
	@echo ""
	@echo "✅  Open: http://127.0.0.1:8090/dev-ui/?app=app"
	@echo "    1. Select 'agent' folder from the dropdown"
	@echo "    2. Type: Review PR #17 on demo-paymentservice"
	@echo "    3. Watch each node execute in real time"
	@echo "    4. Approve/reject HITL escalation when prompted"

# Mock playground — for judges or CI with no API keys
# Uses local eval dataset files instead of real GitHub MCP and Gemini
playground-mock:
	@echo "Starting ReviewGuard in MOCK mode..."
	@echo "No API keys needed — uses local eval datasets"
	@echo ""
	REVIEWGUARD_MOCK=true agents-cli playground --port 8090
	@echo ""
	@echo "✅  Open: http://127.0.0.1:8090/dev-ui/?app=app"
	@echo "    Type: Review PR scenario: partial_pr"

# Single non-interactive run (for CI smoke test)
run:
	REVIEWGUARD_MOCK=true uv run python -m agent.agent \
		--mock-scenario evals/datasets/partial_pr.json

# ─────────────────────────────────────────────────────────────────────────────
# EVALUATION — run this before recording video to show scorecard
# ─────────────────────────────────────────────────────────────────────────────
eval-traces:
	@echo "Generating evaluation traces..."
	uv run python evals/generate_traces.py
	@echo "✅  Traces written to artifacts/traces/generated_traces.json"

eval-grade:
	@echo "Grading traces with LLM-as-judge..."
	agents-cli eval run --config evals/eval_config.yaml

eval: eval-traces eval-grade

# ─────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT — Cloud Run via agents-cli (shown in video)
# ─────────────────────────────────────────────────────────────────────────────
deploy:
	@echo "Deploying ReviewGuard to Cloud Run..."
	agents-cli deploy --platform cloud-run
	@echo "✅  Deployment complete"
