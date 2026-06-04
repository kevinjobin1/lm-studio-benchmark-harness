"""
Unit tests for apps/cli/scoring.py — specifically _detect_failures word-boundary behavior.

Verifies that compound names like 'useStateful' do NOT trigger false-positive
MISSING_IMPORT failures after the \b word-boundary fix, while standalone
API names without imports still correctly trigger.
"""

import unittest

from scoring import CodeScorer, FailureType


class TestDetectFailuresHallucinatedAPIs(unittest.TestCase):
    """Regression tests for the hallucinated-API substring fix in _detect_failures.

    The fix changed:
        if api in code and "import" not in code[:code.find(api)]:
    to:
        pattern = re.compile(r'\b' + re.escape(api) + r'\b')
        match = pattern.search(code)
        if match and "import" not in code[:match.start()]:
    """

    def setUp(self):
        self.scorer = CodeScorer()
        # _detect_failures is private but accessible — Python naming convention only
        self.detect = self.scorer._detect_failures

    # ── False-positive regression tests: compound names must NOT trigger ──

    def test_use_stateful_not_flagged(self):
        """'useStateful' contains 'useState' as a substring, but the \b
        word boundary should prevent matching. No MISSING_IMPORT."""
        code = "const hook = useStateful();"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT, failures, "'useStateful' should NOT trigger MISSING_IMPORT"
        )

    def test_use_effectful_not_flagged(self):
        """'useEffectful' contains 'useEffect' as a substring."""
        code = "const hook = useEffectful();"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT, failures, "'useEffectful' should NOT trigger MISSING_IMPORT"
        )

    def test_use_queryable_not_flagged(self):
        """'useQueryable' contains 'useQuery' as a substring."""
        code = "const result = useQueryable();"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT, failures, "'useQueryable' should NOT trigger MISSING_IMPORT"
        )

    def test_injectable_base_not_flagged(self):
        """'InjectableBase' contains 'Injectable' as a prefix, but \b
        prevents matching (B follows e, so \b fails)."""
        code = "class InjectableBase { }"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "'InjectableBase' should NOT trigger MISSING_IMPORT",
        )

    def test_controller_factory_not_flagged(self):
        """'ControllerFactory' contains 'Controller' as a prefix."""
        code = "const factory = new ControllerFactory();"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "'ControllerFactory' should NOT trigger MISSING_IMPORT",
        )

    def test_base_controller_not_flagged(self):
        """'BaseController' contains 'Controller' as a suffix, but \b
        at 'C' fails because preceded by 'e' (word char)."""
        code = "class BaseController { }"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "'BaseController' should NOT trigger MISSING_IMPORT",
        )

    def test_use_stateful_variable_not_flagged(self):
        """A more realistic variable name like 'useStatefulCounter' should
        also not trigger."""
        code = "const useStatefulCounter = 0;"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "'useStatefulCounter' should NOT trigger MISSING_IMPORT",
        )

    def test_all_compound_names_together_not_flagged(self):
        """Multiple compound names in a single code snippet — none should trigger."""
        code = """
function useStatefulComponent() {
  const useEffectfulHook = useQueryable();
  class InjectableBase extends BaseController { }
}
""".strip()
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT, failures, "No compound names should trigger MISSING_IMPORT"
        )

    # ── Positive tests: standalone names without import MUST still trigger ──

    def test_standalone_use_state_without_import_flagged(self):
        """'useState' as a standalone word without an import should still
        trigger MISSING_IMPORT (regression check)."""
        code = "const [count, setCount] = useState(0);"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone 'useState' without import SHOULD trigger MISSING_IMPORT",
        )

    def test_standalone_use_effect_without_import_flagged(self):
        """'useEffect' as a standalone word without an import."""
        code = "useEffect(() => {}, []);"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone 'useEffect' without import SHOULD trigger MISSING_IMPORT",
        )

    def test_standalone_injectable_without_import_flagged(self):
        """'Injectable' as a standalone word without an import."""
        code = "@Injectable()\nexport class MyService {}"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone '@Injectable()' without import SHOULD trigger MISSING_IMPORT",
        )

    def test_standalone_controller_without_import_flagged(self):
        """'Controller' as a standalone word without an import."""
        code = "@Controller('api')\nexport class MyController {}"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone '@Controller' without import SHOULD trigger MISSING_IMPORT",
        )

    def test_standalone_use_query_without_import_flagged(self):
        """'useQuery' as a standalone word without an import."""
        code = "const { data } = useQuery('key', fetchData);"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone 'useQuery' without import SHOULD trigger MISSING_IMPORT",
        )

    # ── Import-aware tests: standalone names WITH import should NOT trigger ──

    def test_use_state_with_import_not_flagged(self):
        """'useState' with a preceding import should NOT trigger."""
        code = """import { useState } from 'react';
const [count, setCount] = useState(0);"""
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "'useState' WITH import should NOT trigger MISSING_IMPORT",
        )

    def test_use_effect_with_import_not_flagged(self):
        """'useEffect' with a preceding import."""
        code = """import { useEffect } from 'react';
useEffect(() => {}, []);"""
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "'useEffect' WITH import should NOT trigger MISSING_IMPORT",
        )

    def test_mixed_compound_and_standalone(self):
        """A real-world scenario: both 'useStateful' (compound) and
        'useState' (standalone, no import) in the same code."""
        code = """
const useStatefulCounter = 0;
const [count, setCount] = useState(0);
""".strip()
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone 'useState' without import should still trigger "
            "even when 'useStateful' is also present",
        )

    def test_mixed_compound_and_imported_standalone(self):
        """Both 'useStateful' and imported 'useState' — no MISSING_IMPORT."""
        code = """import { useState } from 'react';
const useStatefulCounter = 0;
const [count, setCount] = useState(0);"""
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Neither 'useStateful' nor imported 'useState' should trigger",
        )

    def test_use_queryable_with_standalone_use_query(self):
        """'useQueryable' should not trigger; standalone 'useQuery' without
        import should trigger."""
        code = """
const queryable = useQueryable();
const { data } = useQuery('key', fetchData);
""".strip()
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.MISSING_IMPORT,
            failures,
            "Standalone 'useQuery' without import should trigger",
        )

    # ── Edge cases ──

    def test_empty_code_no_failures(self):
        """Empty code string should return no failures."""
        failures = self.detect("", "", [])
        self.assertEqual(failures, [], "Empty code should produce no failures")

    def test_code_with_import_before_all_apis(self):
        """When 'import' appears BEFORE every API usage, no MISSING_IMPORT
        should be raised for any of them."""
        code = """import { useState, useEffect, useQuery } from 'react';
import { Injectable, Controller } from '@nestjs/common';

const [count, setCount] = useState(0);
useEffect(() => {}, []);
const { data } = useQuery('key', fetchData);

@Injectable()
class MyService {}

@Controller('api')
class MyController {}
"""
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.MISSING_IMPORT,
            failures,
            "All APIs have imports — no MISSING_IMPORT should be raised",
        )


class TestDetectFailuresStaleClosure(unittest.TestCase):
    """Regression tests for the stale-closure substring fix in _detect_failures.

    The fix changed:
        if "useEffect" in code and "[]" in code and "function()" in code:
    to:
        if re.search(r'\\buseEffect\\b', code) and "[]" in code and "function()" in code:
    """

    def setUp(self):
        self.scorer = CodeScorer()
        self.detect = self.scorer._detect_failures

    # ── False-positive regression tests: compounds must NOT trigger STALE_CLOSURE ──

    def test_use_effectful_not_flagged_as_stale_closure(self):
        """'useEffectful' contains 'useEffect' as a substring, but the \b
        boundary prevents matching. No STALE_CLOSURE."""
        code = "const useEffectful = function() { return [1, 2]; };"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.STALE_CLOSURE, failures, "'useEffectful' should NOT trigger STALE_CLOSURE"
        )

    def test_use_effectful_component_not_flagged(self):
        """'useEffectfulComponent' should not trigger stale closure."""
        code = """
function useEffectfulComponent() {
  const data = [1, 2, 3];
  return function() { return data; };
}
""".strip()
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.STALE_CLOSURE,
            failures,
            "'useEffectfulComponent' should NOT trigger STALE_CLOSURE",
        )

    def test_effect_middle_of_word_not_flagged(self):
        """'useEffect' inside a longer camelCase identifier should not trigger."""
        code = """
function myUseEffectHandler() {
  const items = [1, 2];
  return function() { return items; };
}
""".strip()
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.STALE_CLOSURE,
            failures,
            "'useEffect' inside 'myUseEffectHandler' should NOT trigger STALE_CLOSURE",
        )

    # ── Positive tests: standalone useEffect with deps and function SHOULD trigger ──

    def test_standalone_use_effect_stale_closure_flagged(self):
        """Standalone 'useEffect' with '[]' deps and 'function()' callback
        should still trigger STALE_CLOSURE (regression check)."""
        code = "useEffect(function() {}, []);"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.STALE_CLOSURE,
            failures,
            "Standalone 'useEffect' with [] deps and function() SHOULD trigger STALE_CLOSURE",
        )

    def test_use_effect_stale_closure_multi_line_flagged(self):
        """A multi-line useEffect with dependencies array and function."""
        code = """
useEffect(function() {
  fetchData();
}, []);
""".strip()
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.STALE_CLOSURE,
            failures,
            "Multi-line useEffect with [] should trigger STALE_CLOSURE",
        )

    def test_use_effect_with_deps_not_stale(self):
        """useEffect WITH dependencies in the array should also trigger —
        the check only looks for '[]' (empty array), but this verifies
        the detect pattern still works with non-empty arrays.
        Actually this has [dep] not [], so it does NOT trigger."""
        code = "useEffect(function() {}, [dep]);"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.STALE_CLOSURE,
            failures,
            "useEffect with non-empty deps should NOT trigger STALE_CLOSURE",
        )

    # ── Mixed compound and standalone ──

    def test_mixed_use_effectful_and_standalone(self):
        """Both 'useEffectful' and standalone 'useEffect' with [] and
        function() — only the standalone should trigger."""
        code = """
const useEffectful = function() { return [1, 2]; };
useEffect(function() {
  fetchData();
}, []);
""".strip()
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.STALE_CLOSURE,
            failures,
            "Standalone 'useEffect' with [] should trigger STALE_CLOSURE "
            "even when 'useEffectful' is also present",
        )


class TestDetectFailuresAsyncAwait(unittest.TestCase):
    """Regression tests for the async/await substring fix in _detect_failures.

    The fix changed:
        if "async" in code and "await" not in code:
    to:
        if re.search(r'\\basync\\b', code) and not re.search(r'\\bawait\\b', code):
    """

    def setUp(self):
        self.scorer = CodeScorer()
        self.detect = self.scorer._detect_failures

    # ── False-positive regression tests: compounds must NOT trigger WRONG_ASYNC_USAGE ──

    def test_asynchronous_not_flagged(self):
        """'asynchronous' contains 'async' as a substring, but \b boundary
        prevents matching. No WRONG_ASYNC_USAGE."""
        code = "const fn = asynchronous.bind(ctx);"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'asynchronous' should NOT trigger WRONG_ASYNC_USAGE",
        )

    def test_async_function_wrapper_not_flagged(self):
        """'asyncFunctionWrapper' contains 'async' as a substring."""
        code = "const result = asyncFunctionWrapper();"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'asyncFunctionWrapper' should NOT trigger WRONG_ASYNC_USAGE",
        )

    def test_async_helper_not_flagged(self):
        """'asyncHelper' contains 'async' as a prefix."""
        code = "const asyncHelper = createHandler();"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'asyncHelper' should NOT trigger WRONG_ASYNC_USAGE",
        )

    def test_awaitable_alone_no_async_not_flagged(self):
        """'awaitable' contains 'await' as a substring, but \b prevents
        matching. Without any 'async' keyword at all, nothing triggers."""
        code = "const result = awaitable.call(ctx);"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'awaitable' without 'async' should not trigger anything",
        )

    # ── Positive tests: async without await SHOULD trigger ──

    def test_async_function_no_await_flagged(self):
        """Standalone 'async' keyword without 'await' should trigger."""
        code = "async function fetchData() { return data; }"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'async' without 'await' SHOULD trigger WRONG_ASYNC_USAGE",
        )

    def test_async_arrow_no_await_flagged(self):
        """Async arrow function without await."""
        code = "const fn = async () => { return data; };"
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "Async arrow without 'await' SHOULD trigger WRONG_ASYNC_USAGE",
        )

    def test_async_with_await_not_flagged(self):
        """Async function WITH await should NOT trigger."""
        code = "async function fetchData() { const data = await getData(); return data; }"
        failures = self.detect(code, "", [])
        self.assertNotIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'async' WITH 'await' should NOT trigger WRONG_ASYNC_USAGE",
        )

    # ── Mixed compound and standalone ──

    def test_asynchronous_with_real_async_no_await(self):
        """Code with both 'asynchronous' (compound) and 'async' (standalone
        keyword) without 'await' — should still trigger."""
        code = """
async function fetchData() {
  const result = asynchronous.call(ctx);
  return result;
}
""".strip()
        failures = self.detect(code, "", [])
        self.assertIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "Standalone 'async' without 'await' should trigger "
            "even when 'asynchronous' is also present",
        )

    def test_awaitable_counts_as_not_await(self):
        """'async' keyword with only 'awaitable' (not 'await') should
        trigger WRONG_ASYNC_USAGE. With the old substring 'await' check,
        'awaitable' would falsely cover the 'await' requirement."""
        code = "async function fn() { return awaitable(); }"
        failures = self.detect(code, "", [])
        # 'awaitable' contains 'await' but \b prevents matching,
        # so WRONG_ASYNC_USAGE is raised (correct: no actual await keyword)
        self.assertIn(
            FailureType.WRONG_ASYNC_USAGE,
            failures,
            "'async' with only 'awaitable' should trigger — "
            "\bawait\b doesn't match inside 'awaitable'",
        )


class TestInstructionScorerNoMarkdown(unittest.TestCase):
    """Regression tests for the underscore substring fix in
    InstructionScorer.score_instruction_compliance.

    The fix changed:
        if "**" in response or "```" in response or "_" in response:
    to:
        if "**" in response or "```" in response \
           or re.search(r'(?<!\\w)_\\w+_(?!\\w)', response):

    The old bare '_' in response penalized any underscore,
    including snake_case identifiers like 'my_variable'.
    The new pattern only matches markdown-style _word_ italic.
    """

    def setUp(self):
        from scoring import InstructionScorer

        self.scorer = InstructionScorer()

    def _score(self, response: str) -> float:
        """Helper: compute instruction compliance with no_markdown constraint."""
        return self.scorer.score_instruction_compliance(response, {"no_markdown": True})

    # ── False-positive regression: snake_case must NOT penalize ──

    def test_snake_case_variable_not_penalized(self):
        """'my_variable' contains '_' but NOT as markdown italic.
        The regex pattern (?<!\\w)_\\w+_(?!\\w) should not match
        because '_' is adjacent to word chars on both sides."""
        score = self._score("Use my_variable to store the value.")
        self.assertEqual(
            score, 1.0, "snake_case 'my_variable' should NOT trigger no_markdown penalty"
        )

    def test_multiple_snake_case_not_penalized(self):
        """Multiple snake_case identifiers should not penalize."""
        score = self._score("Set user_name and created_at fields.")
        self.assertEqual(score, 1.0, "Multiple snake_case identifiers should NOT trigger penalty")

    def test_single_underscore_in_text_not_penalized(self):
        """A bare '_' not surrounding any word should not match.
        The pattern requires \w+ between underscores."""
        score = self._score("Use an underscore _ like this.")
        self.assertEqual(score, 1.0, "Bare '_' alone should NOT trigger penalty")

    def test_trailing_underscore_not_penalized(self):
        """'value_' has trailing underscore — not markdown italic."""
        score = self._score("Set the value_ field.")
        self.assertEqual(score, 1.0, "Trailing underscore 'value_' should NOT trigger penalty")

    def test_leading_underscore_not_penalized(self):
        """'_value' has leading underscore — not markdown italic."""
        score = self._score("Use the _value variable.")
        self.assertEqual(score, 1.0, "Leading underscore '_value' should NOT trigger penalty")

    # ── Positive tests: markdown italic SHOULD penalize ──

    def test_single_word_italic_penalized(self):
        """Markdown _italic_ with a single word should match the pattern
        and penalize the score."""
        score = self._score("This is _italic_ text.")
        self.assertEqual(score, 0.5, "Markdown '_word_' should trigger no_markdown penalty")

    def test_multi_word_italic_penalized(self):
        """Markdown _word_ with a single word matches the regex.
        Multi-word _phrase like this_ won't match (only single-word
        patterns are detected), but single-word is the most common form."""
        score = self._score("This is _important_ text.")
        self.assertEqual(score, 0.5, "Markdown '_word_' should trigger no_markdown penalty")

    # ── Other markdown still penalized ──

    def test_bold_still_penalized(self):
        """**bold** should still trigger penalty (unchanged)."""
        score = self._score("This is **bold** text.")
        self.assertEqual(score, 0.5, "'**bold**' should still trigger no_markdown penalty")

    def test_code_block_still_penalized(self):
        """```code``` should still trigger penalty (unchanged)."""
        score = self._score("Use ```code``` blocks.")
        self.assertEqual(score, 0.5, "'```code```' should still trigger no_markdown penalty")

    def test_no_markdown_no_penalty(self):
        """Plain text without any markdown should score 1.0."""
        score = self._score("This is plain text with no formatting.")
        self.assertEqual(score, 1.0, "Plain text should NOT trigger penalty")


if __name__ == "__main__":
    unittest.main()
