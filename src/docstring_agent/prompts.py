JSON_SAFETY_RULES = """
String encoding rules (strictly enforced):
- All string values MUST use double quotes: "value"
- Multi-line text: use \\n escape sequences, never literal line breaks inside strings
- Never use triple quotes (\"\"\" or \'\'\')
- Escape internal double quotes as \\"
- Boolean: true/false (not True/False); null (not None/null)
"""

DOCSTRING_BATCH_PROMPT = """\
You are a senior Python engineer writing professional docstrings.

For each method in the JSON array below, produce a docstring in {style} format.
Return ONLY valid JSON — no markdown fences, no text outside the array.

## Rules
- Each docstring must be a single string with \\n for line breaks.
- Use {style} format for Args/Returns sections.
- If existing_docstring is present, improve it (fix grammar, add missing
  Args/Returns, expand vague summaries). Do not start from scratch.
- Never invent side effects or behaviours not visible in the body.
- Qualified names in output must exactly match input qualified names.
- Return ONLY valid JSON array of objects with keys "qualified_name" and "docstring".

## Input methods
{methods_json}

## Expected output format
[
  {{
    "qualified_name": "MyClass.parse_config",
    "docstring": "Parse config and return its contents.\\n\\nArgs:\\n    path (Path): ..."
  }}
]
""" + JSON_SAFETY_RULES
