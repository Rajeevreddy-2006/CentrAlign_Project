# Milestone Execution Rules

After every completed milestone:
1. Update `PROGRESS.md`.
2. Update `README.md` if setup/usage changed.
3. Append to `DECISIONS.md` for any design choice.
4. Make a small commit with a clear message.
5. Push to `origin main`.

## Strict Directives
- **Never commit secrets**: Never commit API keys or private values. Always rely on `.env.example` and local `.env`.
- **Verified claims only**: Never claim a feature works unless it was run and tested in this environment.
- **Honesty about mocking**: Keep an explicit record of anything hardcoded or mocked in `PROGRESS.md`.
