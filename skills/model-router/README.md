# Model Router Skill for Hermes WebUI

**Intelligent model routing — save money, maintain quality.**

This Hermes skill teaches Hermes Agent to automatically decide whether a task should be handled by:
- 💻 **Local Ollama model** (free, private, fast for simple tasks)
- ☁️ **Cloud API** (OpenAI/Anthropic, stronger for complex tasks)
- 🐴 **Hermes Agent mode** (autonomous multi-step execution)

---

## How It Works

The routing logic in `SKILL.md` teaches Hermes to classify each user message and annotate its response with a routing tag. The Hermes WebUI reads these tags to display which model was used and track costs.

**Routing Priority:**
1. Manual user override (`[local]` / `[API]` / `[Agent]`)
2. Agent keywords → Hermes
3. Code/long-text/attachment → API
4. Everything else → Local (default)

---

## Installation

1. Copy this `model-router/` folder into your Hermes skills directory:
   ```
   ~/.hermes/skills/model-router/
   ```
2. Or import via Hermes WebUI → Skills → Import Skill (.zip)

---

## Configuration

Edit `router_config.json` or configure via Hermes WebUI → Skills → Model Router → Configure:

```json
{
  "local": { "model": "qwen2.5:7b" },
  "api": { "provider": "openai", "model": "gpt-4o-mini" },
  "monthly_budget_usd": 5.0,
  "rules": {
    "code_threshold": true,
    "length_threshold": 500
  }
}
```

---

## Contributing

Found a better routing rule from real usage? Update `SKILL.md` and submit a PR!

This skill is designed to evolve with experience. The "Experience Log" section in `SKILL.md` is where community wisdom accumulates.

---

## License

MIT — free to use, modify, and share.

Built for [Hermes WebUI (Saddle)](https://github.com/songchao4218/hermes-webui) and the Zeroclaw ecosystem.
