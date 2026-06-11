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

DOCSTRING_REPAIR_PROMPT = """\
You are a technical writer performing targeted docstring repairs on Python code.
You will receive a list of methods, each with:
  - An existing docstring that has specific quality problems
  - Explicit instructions describing exactly what to fix
  - Explicit guards describing what to preserve unchanged

Your task: apply only the listed instructions. Do not rewrite sections that
are guarded. Do not add content not requested. Do not change the style of
sections that are passing.

Style convention: {style}

Methods to repair:
{methods_json}

Output ONLY a JSON array. No markdown fences. No explanation outside the array.
Each element must have exactly two keys: "qualified_name" and "docstring".
The "docstring" value is the complete repaired docstring as a single string.
Use \\n for line breaks. Do not include the triple quotes in the value.
Qualified names in output must exactly match input qualified names.

Repair rules:
1. Apply each instruction in full. Do not partially apply an instruction.
2. For each guard: the guarded content must appear in your output unchanged.
   If a guard says "preserve the Returns section exactly", your output must
   contain that section with identical wording.
3. Do not invent behaviour not visible in the body_excerpt.
4. Do not add examples, notes, or references unless explicitly instructed.
5. Maintain the style convention throughout: {style}.
6. Critical instructions (severity="critical") must be fully addressed.
   Major and minor instructions should be addressed but may be kept concise.

{JSON_SAFETY_RULES}
"""
