## 2024-05-24 - Pre-compiling Regex
**Learning:** Found multiple instances of `re.search(r'```(?:json)?\s*(.*?)\s*```', ...)` and other regex usages being compiled repeatedly inside functions (like `extract_json_from_response` in `main.py` and `services/llm.py`). Compiling regexes inline causes unnecessary overhead, especially if called multiple times.
**Action:** Extract and pre-compile regular expressions at the module level using `re.compile()` rather than inside frequently called functions or loops to avoid redundant compilation overhead.
