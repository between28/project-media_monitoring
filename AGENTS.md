# AGENTS.md

## Project
Free media-monitoring automation pipeline for the MOLIT spokesperson office in South Korea.

## Current primary path

The repository now uses the Python/desktop path as the primary workflow.

Primary stack:
- Python
- SQLite
- Windows desktop wrapper
- RSS / sitemap
- Google News

## Current workflow

1. Attach a press release `HWPX`
2. Generate draft search queries automatically
3. Let the operator revise search queries and core keywords
4. Collect related articles until `D+3`
5. Save session outputs under `sessions/<session_id>/`
6. Produce:
   - reference article CSV/Markdown
   - ministerial briefing draft Markdown

## Design principles

- Free tools only
- No paid news APIs
- Prefer deterministic rules over opaque automation
- Keep the operator in the loop for final search-rule approval
- Keep code readable and easy to extend

## Non-goals

- Consumer news UI
- Advanced NLP
- Paid LLM pipelines
- Perfect article-body extraction
- Multi-user permission systems

## Expected repository direction

- Continue improving the Python pipeline and desktop app
- Treat policy-specific search rules as session-level data, not repository defaults
- Avoid adding back old fixed sample topics unless they are clearly marked as examples
