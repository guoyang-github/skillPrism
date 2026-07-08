# External Agent Command

> By default `test-skill` runs in **verify-only mode**: the Agent (or a sub-agent) produces the output and the engine only evaluates it. If you prefer, you can configure an **external agent command** that the engine invokes to produce the output.

## When to use

- You want a clean separation between the measuring engine and the executing agent.
- The current Agent context should not be polluted with task-specific reasoning.
- You have a dedicated agent process, LLM wrapper, or sandbox that should execute the task.

## How it works

```text
1. Engine reads the task spec and builds the prompt.
2. Engine calls the command configured in SKILLPRISM_AGENT_COMMAND.
3. The command receives the prompt on stdin and the I/O paths via env vars.
4. The command writes the result to SKILLPRISM_OUTPUT_PATH.
5. Engine evaluates the output.
```

## Configuration

Set the environment variable:

```bash
export SKILLPRISM_AGENT_COMMAND="python examples/editor_wrappers/agent_caller.py"
```

Then run `test-skill` as usual:

```bash
test-skill --skill my-skill --task csv_summary
```

When `SKILLPRISM_AGENT_COMMAND` is set, the engine automatically switches from verify-only to agent mode. To force verify-only anyway, pass `--verify-only`.

## Command interface

The external command must:

- Read the task prompt from `stdin`.
- Read `SKILLPRISM_INPUT_PATH` for the concrete input file.
- Write the result to `SKILLPRISM_OUTPUT_PATH`.
- Exit with code 0 on success.

## Example reference implementation

See `examples/editor_wrappers/agent_caller.py`.

## Relationship to other modes

| Mode | Trigger | Who produces the result |
|---|---|---|
| Verify-only | Default (no `SKILLPRISM_AGENT_COMMAND`, no `--code`) | Current Agent / sub-agent |
| External agent | `SKILLPRISM_AGENT_COMMAND` set | Configured external command |
| Code | `--code <path>` | Engine executes the provided code |

The three modes are mutually exclusive; `--code` and explicit `--verify-only` take precedence over `SKILLPRISM_AGENT_COMMAND`.
