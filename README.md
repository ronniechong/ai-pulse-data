# ai-pulse-data

Fetchers, transforms, workflow, prompts, evals, and committed JSON snapshots
for [AI Pulse](https://github.com/ronniechong/ai-pulse-web) — a dashboard
tracking which AI models the world actually uses (rankings, provider share,
open vs closed source, geographic adoption), with an AI-generated daily
commentary layer.

Runs on a daily GitHub Actions cron: fetch → validate → normalize → diff →
commentary → commit. Data is served straight off this repo via
`raw.githubusercontent.com` / jsDelivr — no separate hosting.

Planning, architecture, and decision log are tracked outside this repo.
