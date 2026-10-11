# Agent Operating Rules & Engineering Guidelines

After every completed milestone:
1. Update `PROGRESS.md`.
2. Update `README.md` if setup/usage changed.
3. Append to `DECISIONS.md` for any design choice.
4. Make a small commit with a clear message.
5. Push to `origin main`.

## Strict Directives
- **Never commit secrets**: Zero credentials, tokens, or private environment files committed to git.
- **Verification over assumption**: Never claim a feature works unless it was actively run and tested.
- **Transparency on mocks**: Keep a list of anything hardcoded or mocked, and be honest about it.
