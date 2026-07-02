---
name: data_pipeline_agent
description: Automatically clean raw news feeds, filter nan values, suppress long headline summaries, and run adaptive database schema mapping.
---

# Data Pipeline Agent Skill

This skill extends Antigravity Agent with data pipeline sanitization and file auditing tools.

## Skill Features
1. **File Hash Monitoring**: Calculates SHA-256 signatures to detect changes.
2. **Nan & Bracket Cleaning**: Sanitizes text payloads to eradicate null or brackets.
3. **Adaptive Summarization**: Implements Condition A & B length truncation for news streams.

## Reference Executable Scripts
All python tools are implemented under the `scripts/` directory:
- [pipeline_tools.py](file:///c:/Users/Chen/OneDrive/桌面/ZHHF/Data%20Dashboard/.agents/skills/data_pipeline_agent/scripts/pipeline_tools.py)
