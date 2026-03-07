# Live E2E Tests

Tests that run against real Claude. They are skipped automatically if neither
auth method is available.

## Auth modes

### Option A — API key
Set `ANTHROPIC_API_KEY` and run:
```bash
ANTHROPIC_API_KEY=sk-ant-... pytest tests/live/ -v
```

### Option B — Claude.ai subscription (Claude Code)
If you have Claude Code installed and are logged in (`claude login`), no key is
needed. The `claude` CLI handles auth via your subscription:
```bash
pytest tests/live/ -v
```

To check which mode will be used:
```bash
python -c "from tests.live.conftest import _has_api_key, _has_claude_cli; \
print('API key:', _has_api_key(), '| CLI:', _has_claude_cli())"
```

## Notes
- Each test creates isolated storage in `tmp_path` — no cross-test state
- API key mode consumes ~1–3 Claude API calls per test
- Subscription mode uses your Claude.ai plan allowance
- Tests are skipped automatically when neither auth method is available
