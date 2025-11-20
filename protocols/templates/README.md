# Protocol Templates

Templates convert structured YAML into protocol implementations at runtime.
Every file in this directory must conform to the schema implemented in
`protocols/template_runtime/schema.py`.

## Authoring Guidelines

- Keep values numeric (no hex literals) so scaling rules stay explicit.
- If the send frame needs a new transformation, extend the schema and add a
	handler in `adapters/template_protocol.py` rather than embedding ad-hoc logic
	in YAML.
- Use descriptive `label` values because they surface directly in parsed
	dictionaries and UI tables.
- Add a regression test under `tests/template_protocol/` whenever a template is
	updated.

See `acusim.yaml` for a comprehensive example.

