# Active Context

**Date:** {{DATE}}

We have restarted the project, using `oldproject/` as reference only.  `newproject/` will house the fresh, async-first BlazeAI Lite bot.

## Current Focus
1. Establish Memory Bank files (this document).
2. Produce reference docs that capture oldproject architecture & pitfalls.
3. Draft foundational patterns and tech stack (done).
4. Next: scaffold minimal async code skeleton (`/src`) and CI pipeline.

## Recent Decisions
* Use `aiohttp` + `aiogram` instead of synchronous `requests` + `python-telegram-bot`.
* Always validate mint length before hitting Helius.
* Rotate RPC endpoints via adapter list.

## Next Steps
1. Create `/newproject/reference/oldproject_summary.md` summarising modules & mistakes.
2. Generate `README.md` with setup instructions.
3. Commit initial `requirements.txt`.

--- 