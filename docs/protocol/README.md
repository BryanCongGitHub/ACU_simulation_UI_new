# Protocol Template System

The ACU simulator now reads protocol definitions from YAML templates rather than
hard coded Python classes.  The runtime lives under
`protocols/template_runtime/` and converts the YAML schema into
`TemplateProtocol` instances that implement the original `BaseProtocol`
interface.

## Layout

```
protocols/
  templates/              # YAML definitions (see acusim.yaml)
  template_runtime/
     adapters/             # TemplateProtocol implementation
     loader.py             # YAML loader + cache
     schema.py             # Dataclasses and validation helpers
```

Each template file describes the frame lengths, send-frame operations, and
receive-frame parsing rules.  Categories (INV / CHU / BCC) share the same send
layout but may expose different parsing metadata such as status flags or fault
messages.

The optional `send_layout` section captures human-readable metadata for the
send frame (byte offsets, bit meanings, scaling, etc.).  The runtime currently
ignores this block, but it serves as authoritative documentation and can power
future UI automation.

## Editing Flow

1. Update or add a file in `protocols/templates/`.
2. Run `pytest tests/template_protocol` to ensure the template matches legacy
    behaviour.
3. If a template introduces new send operations or parse rules, extend the
    dataclasses in `schema.py` and the handlers in `adapters/template_protocol.py`.

Refer to `docs/protocol/examples/acusim.md` for a walkthrough of the INV-like
template.
