# SKILL.md Editor Wrappers

These example scripts implement the interface expected by
`improve-skill --auto-edit`:

- Read a prompt from **stdin**.
- Return the complete updated **SKILL.md** content to **stdout**.
- Do not wrap the output in Markdown code fences.

## Usage

Pick a provider, install its dependency, set the API key / model, and point
`SKILLPRISM_EDITOR_COMMAND` at the script:

```bash
# OpenAI
pip install openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_editor.py"

# Anthropic
pip install anthropic
export ANTHROPIC_API_KEY=...
export ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/anthropic_editor.py"

# OpenAI-compatible Chinese providers (Moonshot/Kimi, DeepSeek, Zhipu GLM, Alibaba Qwen)
pip install openai
export OPENAI_API_KEY=<your-provider-key>
export OPENAI_BASE_URL=https://api.moonshot.cn/v1
export OPENAI_MODEL=moonshot-v1-8k
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/openai_compatible_editor.py"

# Local Ollama
pip install requests
export OLLAMA_MODEL=llama3
export SKILLPRISM_EDITOR_COMMAND="python examples/editor_wrappers/ollama_editor.py"
```

Then run autonomous optimization:

```bash
improve-skill skills/<skill> \
  --record-baseline \
  --auto-edit \
  --apply \
  --max-rounds 3
```

## Writing Your Own Wrapper

### Chinese provider examples via `openai_compatible_editor.py`

Most Chinese LLM APIs are OpenAI-compatible. Use the same wrapper and only
change `OPENAI_BASE_URL` and `OPENAI_MODEL`:

```bash
# Moonshot (Kimi)
export OPENAI_BASE_URL=https://api.moonshot.cn/v1
export OPENAI_MODEL=moonshot-v1-8k

# DeepSeek
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-chat

# Zhipu AI (GLM)
export OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
export OPENAI_MODEL=glm-4-flash

# Alibaba DashScope (Qwen)
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export OPENAI_MODEL=qwen-max
```

Any command that reads stdin and prints Markdown will work. The prompt sent by
skillPrism includes:

- The skill name and current rubric score.
- The weakest dimension and its score.
- Concrete editing strategy for that dimension.
- The current SKILL.md content.

You can also add a wrapper that deterministically edits the file (no LLM) for
reproducible benchmark or testing scenarios.
