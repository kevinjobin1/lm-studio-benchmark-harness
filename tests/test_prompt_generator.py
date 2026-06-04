"""
Unit tests for prompt_generator.py engines:
paraphrase, substitute_variables, mutate_context.

Uses deterministic seeds to verify behavior despite internal randomness.
"""

import unittest

from prompt_generator import PromptGenerator, GeneratedPrompt, PromptCategory


# ── Shared fixtures ───────────────────────────────────────────────────

SAMPLE_PROMPT = """\
Implement a React component for user profiles with TypeScript types.

The component should handle loading, error, and empty states.
Use proper hooks and follow React best practices.

Requirements:
- TypeScript interfaces for props
- Error boundaries
- Loading skeleton
"""

CODE_PROMPT = """\
Fix this TypeScript function:

```typescript
function processData<T>(data: T): T {
  return data.toUpperCase();
}
```

The function should accept only string types.
"""

NESTJS_PROMPT = """\
Create a NestJS service for user management with JWT authentication.

The service should use @Injectable() decorator and proper dependency injection.
Implement a controller with @Controller() and proper guards.
"""

REACT_PROMPT = """\
Build a React component with useState and useEffect hooks.

The component should fetch data and display it with proper loading states.
Use TypeScript interfaces for all props and state.
"""

TYPESCRIPT_PROMPT = """\
Write a TypeScript utility type using generics and conditional types.

The type should use extends constraints and mapped types.
Include proper type guards for runtime validation.
"""


# ── Tests ─────────────────────────────────────────────────────────────


class TestParaphraseEngine(unittest.TestCase):
    """Tests for PromptGenerator.paraphrase() — synonym-based rewording."""

    def setUp(self):
        self.gen = PromptGenerator(seed=42)

    def test_intensity_zero_returns_unchanged(self):
        """intensity=0 should return the exact same string."""
        result = self.gen.paraphrase(SAMPLE_PROMPT, intensity=0.0)
        self.assertEqual(result, SAMPLE_PROMPT)

    def test_intensity_one_makes_changes(self):
        """intensity=1.0 should produce a different string."""
        # Use a minimal prompt with a known action verb at max intensity.
        # At intensity=1.0, action verbs always fire (random < 1.0 is always True).
        prompt = "Implement a function. Explain the component."
        gen = PromptGenerator(seed=123)
        result = gen.paraphrase(prompt, intensity=1.0)
        self.assertNotEqual(
            result, prompt, f"intensity=1.0 should change the prompt, got identical: {result[:50]}"
        )
        # At intensity 1.0, at least one action verb should vanish
        changed = not ("Implement" in result and "Explain" in result)
        self.assertTrue(changed, f"At intensity=1.0, at least one action verb should be replaced")

    def test_intensity_one_deterministic_with_seed(self):
        """Same seed + same input = same output."""
        gen_a = PromptGenerator(seed=99)
        gen_b = PromptGenerator(seed=99)
        result_a = gen_a.paraphrase(SAMPLE_PROMPT, intensity=0.8)
        result_b = gen_b.paraphrase(SAMPLE_PROMPT, intensity=0.8)
        self.assertEqual(result_a, result_b)

    def test_empty_prompt_returns_empty(self):
        """Empty string should remain empty."""
        result = self.gen.paraphrase("", intensity=0.5)
        self.assertEqual(result, "")

    def test_replaces_implement_with_synonym(self):
        """Known action verb 'implement' should be replaced at sufficient intensity."""
        prompt = "Implement a service for data processing."
        gen = PromptGenerator(seed=7)
        result = gen.paraphrase(prompt, intensity=1.0)

        # At intensity 1.0, "Implement" should be replaced
        self.assertNotIn("Implement", result)

    def test_replaces_noun_with_synonym(self):
        """Nouns in NOUN_SYNONYMS should be replaced at high intensity."""
        # Include "Implement" (action verb, always fires at intensity=1.0) to guarantee
        # at least one change, plus multiple nouns for noun replacement coverage.
        prompt = "Implement a component function for the database service endpoint."
        gen = PromptGenerator(seed=42)
        result = gen.paraphrase(prompt, intensity=1.0)

        # "Implement" in ACTION_SYNONYMS guarantees at least one change at intensity=1.0
        self.assertNotEqual(
            result, prompt, "At intensity 1.0 with action verb, prompt should change"
        )

    def test_low_intensity_preserves_synonym_words(self):
        """At low intensity (0.1), words that COULD be replaced should mostly be preserved."""
        # This prompt contains words in ACTION_SYNONYMS (Implement, explain)
        # and NOUN_SYNONYMS (component, function, service)
        prompt = "Implement a component function. Explain the service."
        gen = PromptGenerator(seed=12345)
        result = gen.paraphrase(prompt, intensity=0.1)

        # At intensity 0.1, max_changes ≈ 1, so at most 1 word changes.
        # Most synonym-mapped words should survive.
        preserved = sum(1 for w in ["Implement", "component", "function", "service"] if w in result)
        self.assertGreaterEqual(
            preserved, 3, f"Low intensity should preserve most words, but only {preserved}/4 remain"
        )

    def test_no_substring_corruption_in_longer_words(self):
        """Words like 'functionality', 'serviceable', 'implementation' that
        CONTAIN synonym keys as substrings should NOT have them replaced.
        This verifies the word-boundary fix (ghost \b) in _has_word()."""
        prompt = (
            "The database functionality was implemented for the microcomponent. "
            "The serviceable endpoint handled the prefix correctly. "
            "The implementation was functional."
        )
        gen = PromptGenerator(seed=42)
        result = gen.paraphrase(prompt, intensity=1.0)

        # Longer words containing synonym substrings should remain intact
        self.assertIn(
            "functionality", result, "'functionality' should NOT have 'function' replaced inside it"
        )
        self.assertIn(
            "serviceable", result, "'serviceable' should NOT have 'service' replaced inside it"
        )
        self.assertIn(
            "implementation",
            result,
            "'implementation' should NOT have 'implement' replaced inside it",
        )
        self.assertIn(
            "microcomponent",
            result,
            "'microcomponent' should NOT have 'component' replaced inside it",
        )
        self.assertIn("prefix", result, "'prefix' should NOT have 'fix' replaced inside it")
        self.assertIn(
            "functional", result, "'functional' should NOT have 'function' replaced inside it"
        )

    def test_mixed_long_and_short_words_no_corruption(self):
        """A prompt with BOTH standalone synonyms AND longer containing-words
        should only replace the standalone ones — longer words stay untouched.
        The prompt is 6 words, so max_changes=1 at intensity=1.0 — only the
        first action verb "Implement" fires, and "microcomponent" is preserved."""
        prompt = "Implement a microcomponent for the service."
        gen = PromptGenerator(seed=999)
        result = gen.paraphrase(prompt, intensity=1.0)

        # Standalone "Implement" should be replaced at intensity=1.0
        self.assertNotIn("Implement", result, "Standalone 'Implement' should be replaced")

        # "microcomponent" should NOT be corrupted
        self.assertIn(
            "microcomponent",
            result,
            "'microcomponent' should NOT have 'component' replaced inside it",
        )


class TestSubstituteVariablesEngine(unittest.TestCase):
    """Tests for PromptGenerator.substitute_variables() — identifier/type swapping."""

    def setUp(self):
        self.gen = PromptGenerator(seed=42)

    def test_intensity_zero_returns_unchanged(self):
        """intensity=0 should return the exact same string."""
        result = self.gen.substitute_variables(SAMPLE_PROMPT, intensity=0.0)
        self.assertEqual(result, SAMPLE_PROMPT)

    def test_intensity_one_makes_changes(self):
        """intensity=1.0 should produce a different string when camelCase identifiers exist."""
        # SAMPLE_PROMPT has no camelCase identifiers, so use one that does
        prompt = "function processData(userProfile: string) { return userProfile; }"
        gen = PromptGenerator(seed=42)
        result = gen.substitute_variables(prompt, intensity=1.0)
        self.assertNotEqual(
            result, prompt, f"intensity=1.0 should change identifiers, got identical result"
        )

    def test_deterministic_with_same_seed(self):
        """Re-creating generator with same seed produces same output for same input."""
        prompt = "function processData(userProfile: string) { return userProfile; }"
        gen = PromptGenerator(seed=77)
        result1 = gen.substitute_variables(prompt, intensity=1.0)
        # Re-create with same seed — should get identical result
        gen2 = PromptGenerator(seed=77)
        result2 = gen2.substitute_variables(prompt, intensity=1.0)
        self.assertEqual(
            result1, result2, f"Same seed should produce same result:\n  {result1}\n  {result2}"
        )

    def test_empty_prompt_returns_empty(self):
        """Empty string should remain empty."""
        result = self.gen.substitute_variables("", intensity=0.5)
        self.assertEqual(result, "")

    def test_replaces_long_camelcase_identifier(self):
        """Long camelCase identifiers (>5 chars) should be replaced at intensity=1.0."""
        # Use an identifier NOT in IDENTIFIER_NAMES so random.choice can't pick the same word.
        # Only ONE occurrence so .replace(word, _, 1) fully removes it.
        prompt = "const customerData: string = 'hello';"
        gen = PromptGenerator(seed=5)
        result = gen.substitute_variables(prompt, intensity=1.0)

        # customerData is 12 chars camelCase, should be replaced at intensity 1.0
        self.assertNotIn("customerData", result)

    def test_does_not_replace_short_camelcase(self):
        """Short camelCase identifiers (≤5 chars) should NOT be replaced."""
        prompt = "const xVal = 42; const myId = 'test';"
        gen = PromptGenerator(seed=42)
        result = gen.substitute_variables(prompt, intensity=1.0)

        # myId is 4 chars, xVal is 4 chars — both ≤ 5, should be preserved
        self.assertIn("myId", result)
        self.assertIn("xVal", result)

    def test_replaces_function_name_pattern(self):
        """Function-like words (ending in Data/Request/Records/etc.) should be replaced."""
        prompt = "Call processData to handle the incoming data."
        gen = PromptGenerator(seed=3)
        result = gen.substitute_variables(prompt, intensity=1.0)

        # processData matches the function name pattern
        self.assertNotIn("processData", result)

    # ── Substring-protection tests for substitute_variables ──

    def test_compound_camelcase_contains_identifier_prefix(self):
        """A longer camelCase word like 'userIdValidator' contains 'userId'
        (an IDENTIFIER_NAME) as a prefix. The whole word should be treated
        as a single token — 'userId' inside it should NOT be independently
        replaced, which would produce 'customerIdValidator'."""
        prompt = "Use the userIdValidator for validation."

        # At intensity=1.0, the compound word may be replaced as a whole,
        # but must NOT be partially corrupted
        result = self.gen.substitute_variables(prompt, intensity=1.0)

        # Verify no partial corruption patterns exist
        partial_fragments = ["customerIdValidator", "orderRefValidator", "sessionTokenValidator"]
        for frag in partial_fragments:
            self.assertNotIn(
                frag, result, f"'userIdValidator' must not be partially corrupted to '{frag}'"
            )

    def test_standalone_identifier_alongside_compound(self):
        """A prompt with both standalone 'userId' AND compound 'userIdValidator'
        should process each independently. The standalone gets replaced on its
        own, the compound either stays or is replaced as a whole."""
        prompt = "Check userId and userIdValidator."
        result = self.gen.substitute_variables(prompt, intensity=1.0)

        # The compound should NOT become something like "customerIdValidator"
        self.assertNotIn(
            "customerIdValidator",
            result,
            "Standalone 'userId' replacement should not corrupt 'userIdValidator'",
        )

    def test_compound_function_name_no_partial_corruption(self):
        """A longer word like 'processDataHandler' contains 'processData'
        (a FUNCTION_NAME) as a prefix. The function name regex uses \b
        boundaries, so 'processDataHandler' is NOT matched by the function
        name pattern — it's handled as a single camelCase token instead."""
        prompt = "Call processDataHandler with args."
        result = self.gen.substitute_variables(prompt, intensity=1.0)

        # 'processDataHandler' should either be preserved intact or replaced
        # as a whole — never partially corrupted
        self.assertNotIn(
            "handleRequestHandler",
            result,
            "'processDataHandler' not partially corrupted to 'handleRequestHandler'",
        )
        self.assertNotIn(
            "fetchRecordsHandler",
            result,
            "'processDataHandler' not partially corrupted to 'fetchRecordsHandler'",
        )

    def test_preserves_non_matching_text(self):
        """Common words should not be affected."""
        prompt = "The quick brown fox jumps over the lazy dog."
        gen = PromptGenerator(seed=42)
        result = gen.substitute_variables(prompt, intensity=1.0)

        # No camelCase or function patterns in this sentence
        self.assertEqual(result, prompt)


class TestMutateContextEngine(unittest.TestCase):
    """Tests for PromptGenerator.mutate_context() — framework/tech stack swapping."""

    def setUp(self):
        self.gen = PromptGenerator(seed=42)

    def test_mutate_react_to_vue(self):
        """React prompt should be mutated to Vue 3."""
        result = self.gen.mutate_context(REACT_PROMPT, framework="react")

        # React references should be replaced
        self.assertNotIn("React", result)
        self.assertIn("Vue 3", result)

        # Hook names should be swapped
        self.assertNotIn("useState", result)
        self.assertNotIn("useEffect", result)
        self.assertIn("ref", result)
        self.assertIn("watch", result)

    def test_mutate_nestjs_to_express(self):
        """NestJS prompt should be mutated to Express.js."""
        result = self.gen.mutate_context(NESTJS_PROMPT, framework="nestjs")

        # NestJS references should be replaced.
        # Keyword normalization runs before framework name insertion, so
        # "Express.js" should not be corrupted to "express.js".
        self.assertNotIn("NestJS", result)
        self.assertIn("Express.js", result)

        # Decorators should be mapped
        self.assertNotIn("@Injectable", result)
        self.assertNotIn("@Controller", result)
        self.assertIn("middleware", result.lower())
        self.assertIn("router", result.lower())

    def test_mutate_typescript_to_javascript(self):
        """TypeScript prompt should be mutated to JavaScript."""
        prompt = "Write TypeScript code with interface and type guard."
        result = self.gen.mutate_context(prompt, framework="typescript")

        # TypeScript references should be replaced
        self.assertNotIn("TypeScript", result)
        self.assertIn("JavaScript", result)

        # Patterns should be swapped (singular forms match whole-word)
        self.assertNotIn("interface", result.lower())

    def test_unknown_framework_returns_original(self):
        """Passing a framework not in FRAMEWORK_SWAPS should return unchanged prompt."""
        original = "Write Python code with decorators."
        result = self.gen.mutate_context(original, framework="python")

        self.assertEqual(result, original)

    def test_none_framework_picks_random_and_mutates(self):
        """framework=None should pick a random framework and mutate accordingly."""
        gen = PromptGenerator(seed=42)
        prompt = "Build a React component with TypeScript and NestJS backend."
        result = gen.mutate_context(prompt, framework=None)

        # It should differ from the original (a framework swap was applied)
        self.assertNotEqual(result, prompt, "framework=None should produce a mutation")

        # At least one of the three framework terms should be replaced
        framework_terms = ["React", "NestJS", "TypeScript"]
        unchanged_count = sum(1 for t in framework_terms if t in result)
        self.assertLess(
            unchanged_count,
            3,
            f"None should mutate at least one framework term, but {unchanged_count}/3 remain",
        )

    def test_empty_prompt_returns_empty(self):
        """Empty string should remain empty."""
        result = self.gen.mutate_context("", framework="react")
        self.assertEqual(result, "")

    def test_mutate_does_not_affect_unrelated_text(self):
        """Framework swap should only change target terms, not general text."""
        prompt = "Create a database migration script."
        result = self.gen.mutate_context(prompt, framework="react")

        # No react-specific terms in this prompt, so it should be largely unchanged
        self.assertIn("database", result.lower())
        self.assertIn("migration", result.lower())

    # ── New edge case tests ───────────────────────────────────────

    def test_prompt_with_middleware_keyword_before_mutation(self):
        """A NestJS prompt that already contains 'middleware' should have
        it preserved (keyword normalization matches and rewrites to same word).
        The hook swap also inserts 'middleware' from @Injectable."""
        prompt = "Create a NestJS middleware for auth. Use @Injectable() and @Controller()."
        result = self.gen.mutate_context(prompt, framework="nestjs")

        # Framework name swapped
        self.assertNotIn("NestJS", result)
        self.assertIn("Express.js", result)

        # 'middleware' should appear AT LEAST TWICE:
        # 1. From the original prompt ("middleware") — preserved by keyword normalization
        # 2. From the hook swap (@Injectable → "middleware")
        middleware_count = result.lower().count("middleware")
        self.assertGreaterEqual(
            middleware_count,
            2,
            f"Expected 'middleware' to appear ≥2 times (original + from @Injectable swap), found {middleware_count}:\n{result}",
        )

        # Original decorators replaced
        self.assertNotIn("@Injectable", result)
        self.assertNotIn("@Controller", result)
        self.assertIn("router", result.lower())

    def test_multiple_framework_references_react_mutation(self):
        """A prompt referencing React, TypeScript, and NestJS should only
        have React-specific terms mutated when framework='react'.
        TypeScript and NestJS terms should be unchanged."""
        prompt = (
            "Build a React component with TypeScript interfaces. "
            "Use useState and useEffect hooks. "
            "The NestJS backend uses @Injectable()."
        )
        result = self.gen.mutate_context(prompt, framework="react")

        # React terms replaced
        self.assertNotIn("React", result)
        self.assertIn("Vue 3", result)
        self.assertNotIn("useState", result)
        self.assertNotIn("useEffect", result)
        self.assertIn("ref", result)
        self.assertIn("watch", result)

        # TypeScript and NestJS terms PRESERVED (not part of react swap)
        self.assertIn(
            "TypeScript", result, "TypeScript should be preserved when mutating react→vue"
        )
        self.assertIn("NestJS", result, "NestJS should be preserved when mutating react→vue")
        self.assertIn(
            "@Injectable", result, "@Injectable should be preserved when mutating react→vue"
        )

    def test_multiple_framework_references_nestjs_mutation(self):
        """A prompt referencing React, TypeScript, and NestJS should only
        have NestJS-specific terms mutated when framework='nestjs'.
        React and TypeScript terms should be unchanged."""
        prompt = (
            "Build a React component with TypeScript interfaces. "
            "Use useState and useEffect hooks. "
            "The NestJS backend uses @Injectable()."
        )
        result = self.gen.mutate_context(prompt, framework="nestjs")

        # NestJS terms replaced
        self.assertNotIn("NestJS", result)
        self.assertIn("Express.js", result)
        self.assertNotIn("@Injectable", result)

        # React and TypeScript terms PRESERVED
        self.assertIn("React", result, "React should be preserved when mutating nestjs→express")
        self.assertIn(
            "TypeScript", result, "TypeScript should be preserved when mutating nestjs→express"
        )
        self.assertIn(
            "useState", result, "useState should be preserved when mutating nestjs→express"
        )
        self.assertIn(
            "useEffect", result, "useEffect should be preserved when mutating nestjs→express"
        )

    def test_multiple_framework_references_typescript_mutation(self):
        """A prompt referencing TypeScript and React should only
        have TypeScript-specific terms mutated when framework='typescript'.
        React terms should be unchanged. Hook chain is now safe —
        'interface' → 'JSDoc @typedef' won't be corrupted by 'type' → 'JSDoc @type'
        since both use whole-word matching."""
        prompt = (
            "Write TypeScript code with interface and type guard. The React component uses props."
        )
        result = self.gen.mutate_context(prompt, framework="typescript")

        # TypeScript framework name replaced
        self.assertNotIn("TypeScript", result)
        self.assertIn("JavaScript", result)

        # Hook chain should NOT corrupt: "interfaces" → "JSDoc @typedefs"
        # The "type" inside "@typedef" must NOT be matched by the next hook
        self.assertNotIn("interface", result.lower(), "'interface' should be replaced by the hooks")
        self.assertIn("@typedef", result, "'JSDoc @typedef' should be intact after hook chain")

        # 'type' as a WHOLE WORD should be replaced to 'JSDoc @type'
        # But 'type' inside 'typedef' should NOT be touched
        self.assertNotIn(" type ", result, "standalone 'type' should be replaced")

        # Verify @typedef is NOT corrupted (contains "typedef" intact, not "@JSDoc @typedef")
        typedef_idx = result.find("@typedef")
        self.assertGreaterEqual(typedef_idx, 0, "@typedef must appear in the result")
        # Check no corruption pattern: "@JSDoc @typedef" would mean "JSDoc @JSDoc @typedef"
        # We just need to verify "@typedef" is followed by non-word char or end-of-string
        # and doesn't contain a second "@JSDoc" before it
        self.assertNotIn(
            "@JSDoc @typedef",
            result,
            "'@typedef' must NOT be corrupted to '@JSDoc @typedef' (hook chain bug)",
        )

        # React terms PRESERVED
        self.assertIn(
            "React", result, "React should be preserved when mutating typescript→javascript"
        )
        self.assertIn(
            "component", result, "component should be preserved when mutating typescript→javascript"
        )

    # ── Substring-protection tests for hooks/patterns whole-word fix ──

    def test_typescript_hook_no_substring_corruption(self):
        """'prototype' containing 'type' and 'subinterface' containing
        'interface' should NOT be corrupted by the typescript hook chain."""
        prompt = "Use prototype and subinterface in this TypeScript code. Also use genericsHandler."
        result = self.gen.mutate_context(prompt, framework="typescript")

        # Longer words containing hook substrings should remain intact
        self.assertIn("prototype", result, "'prototype' should NOT have 'type' replaced inside it")
        self.assertIn(
            "subinterface", result, "'subinterface' should NOT have 'interface' replaced inside it"
        )
        self.assertIn(
            "genericsHandler",
            result,
            "'genericsHandler' should NOT have 'generics' replaced inside it",
        )

        # Standalone hook words in the SAME prompt should still be replaced
        self.assertNotIn("TypeScript", result, "Standalone 'TypeScript' should be replaced")

    def test_typescript_pattern_no_substring_corruption(self):
        """'decoratorFactory' containing 'decorator' should NOT be corrupted
        by the typescript pattern swap."""
        prompt = "Use a decoratorFactory in this TypeScript type guard. "
        result = self.gen.mutate_context(prompt, framework="typescript")

        # 'decorator' inside 'decoratorFactory' should NOT be matched
        self.assertIn(
            "decoratorFactory",
            result,
            "'decoratorFactory' should NOT have 'decorator' replaced inside it",
        )

        # Standalone 'type guard' SHOULD be replaced
        self.assertNotIn("type guard", result, "Standalone 'type guard' should be replaced")

    def test_react_pattern_no_substring_corruption(self):
        """'microcomponent' containing 'component', 'JSXElement' containing
        'JSX', and 'propsBuilder' containing 'props' should NOT be corrupted
        by the react pattern swap."""
        prompt = (
            "Build a microcomponent with JSXElement that uses propsBuilder. "
            "Focus on React and useState."
        )
        result = self.gen.mutate_context(prompt, framework="react")

        # Longer words containing pattern substrings should remain intact
        self.assertIn(
            "microcomponent",
            result,
            "'microcomponent' should NOT have 'component' replaced inside it",
        )
        self.assertIn("JSXElement", result, "'JSXElement' should NOT have 'JSX' replaced inside it")
        self.assertIn(
            "propsBuilder", result, "'propsBuilder' should NOT have 'props' replaced inside it"
        )

        # Standalone terms SHOULD be replaced
        self.assertNotIn("React", result, "Standalone 'React' should be replaced")
        self.assertNotIn("useState", result, "Standalone 'useState' should be replaced")
        self.assertIn("Vue 3", result)
        self.assertIn("ref", result)

    def test_nestjs_pattern_no_substring_corruption(self):
        """'guardian' containing 'guard', 'decoratorFactory' containing
        'decorator', and 'providerFactory' containing 'provider' should NOT
        be corrupted by the nestjs pattern swap."""
        prompt = (
            "The guardian used a decoratorFactory and providerFactory. "
            "Use NestJS with @Injectable()."
        )
        result = self.gen.mutate_context(prompt, framework="nestjs")

        # Longer words containing pattern substrings should remain intact
        self.assertIn("guardian", result, "'guardian' should NOT have 'guard' replaced inside it")
        self.assertIn(
            "decoratorFactory",
            result,
            "'decoratorFactory' should NOT have 'decorator' replaced inside it",
        )
        self.assertIn(
            "providerFactory",
            result,
            "'providerFactory' should NOT have 'provider' replaced inside it",
        )

        # Standalone terms SHOULD be replaced
        self.assertNotIn("NestJS", result, "Standalone 'NestJS' should be replaced")
        self.assertNotIn("@Injectable", result, "Standalone '@Injectable' should be replaced")
        self.assertIn("Express.js", result)
        self.assertIn("middleware", result.lower())

    def test_mixed_hooks_and_longer_words_all_frameworks(self):
        """A prompt referencing ALL three frameworks with both standalone
        hooks AND longer containing-words should only replace standalone
        hooks — longer words stay untouched regardless of framework."""
        prompt = "Use prototype, microcomponent, and guardian. Use React, NestJS, and TypeScript."

        for framework in ["react", "nestjs", "typescript"]:
            with self.subTest(framework=framework):
                result = self.gen.mutate_context(prompt, framework=framework)

                # Longer words should NEVER be corrupted
                self.assertIn(
                    "prototype",
                    result,
                    f"'prototype' should NOT be corrupted when mutating {framework}",
                )
                self.assertIn(
                    "microcomponent",
                    result,
                    f"'microcomponent' should NOT be corrupted when mutating {framework}",
                )
                self.assertIn(
                    "guardian",
                    result,
                    f"'guardian' should NOT be corrupted when mutating {framework}",
                )

    # ── Framework name substring-protection tests ──

    def test_react_framework_name_compound_word(self):
        """'React' inside 'ReactComponent' should NOT be replaced to 'Vue 3'.
        The word boundary \\b prevents matching 'React' when followed by
        a word char like 'C'."""
        prompt = "The ReactComponent pattern is common."
        result = self.gen.mutate_context(prompt, framework="react")

        # The compound word should remain intact (no partial replacement)
        self.assertIn("ReactComponent", result, "'ReactComponent' must not become 'Vue 3Component'")

    def test_react_framework_name_standalone_and_compound(self):
        """A prompt with both standalone 'React' and compound 'ReactComponent'
        should replace 'React' and preserve 'ReactComponent'."""
        prompt = "Use React with ReactComponent."
        result = self.gen.mutate_context(prompt, framework="react")

        # Standalone "React" was replaced to "Vue 3"
        self.assertIn("Vue 3", result)
        # "ReactComponent" is preserved — "React" remains as substring, which is expected
        self.assertIn("ReactComponent", result, "'ReactComponent' must not be corrupted")
        # Verify standalone "React" no longer appears (it was replaced to "Vue 3")
        self.assertNotIn(
            "React with",
            result,
            "Standalone 'React' should be replaced (checking 'React with' as proxy)",
        )

    def test_nestjs_framework_name_compound_word(self):
        """'Nest' inside 'Nesting' should NOT be replaced to 'Express.js'.
        'Nesting' is a real English word, not a NestJS reference."""
        prompt = "The nesting behavior causes issues."
        result = self.gen.mutate_context(prompt, framework="nestjs")

        self.assertNotIn(
            "Express.js",
            result,
            "'Nesting' should NOT become 'Express.jsing' — 'Express.js' shouldn't appear at all",
        )
        self.assertIn("nesting", result.lower(), "'nesting' should remain intact")

    def test_nestjs_framework_name_standalone_and_compound(self):
        """A prompt with both standalone 'NestJS' and compound 'Nesting'
        should replace 'NestJS' and preserve 'Nesting'."""
        prompt = "Use NestJS for the nesting logic."
        result = self.gen.mutate_context(prompt, framework="nestjs")

        self.assertNotIn("NestJS", result, "Standalone 'NestJS' should be replaced")
        self.assertIn("Express.js", result)
        self.assertIn("nesting", result.lower(), "'Nesting' must not become 'Express.jsing'")

    def test_typescript_framework_name_ts_in_compound(self):
        """'TS' inside 'BITS' should NOT be replaced to 'JavaScript'.
        'BITS' contains 'TS' but '\\bTS\\b' doesn't match inside it."""
        prompt = "The BITS configuration is outdated."
        result = self.gen.mutate_context(prompt, framework="typescript")

        self.assertNotIn(
            "JavaScript",
            result,
            "'BITS' contains 'TS' but should NOT trigger TypeScript→JavaScript swap",
        )
        self.assertIn("BITS", result, "'BITS' should remain intact")

    def test_typescript_framework_name_plural_not_matched(self):
        """'TypeScripts' (plural) should NOT be replaced to 'JavaScripts'
        because '\\bTypeScript\\b' doesn't match when 's' follows."""
        prompt = "Multiple TypeScripts were used."
        result = self.gen.mutate_context(prompt, framework="typescript")

        # 'TypeScripts' has 's' after 'TypeScript', so \\b after 't' fails
        self.assertNotIn("JavaScripts", result, "'TypeScripts' should NOT become 'JavaScripts'")

    def test_typescript_framework_name_standalone_and_compound(self):
        """A prompt with standalone 'TypeScript' and compound words containing
        'TS' ('BITS') should replace 'TypeScript' and preserve 'BITS'."""
        prompt = "Use TypeScript with BITS."
        result = self.gen.mutate_context(prompt, framework="typescript")

        self.assertNotIn("TypeScript", result, "Standalone 'TypeScript' should be replaced")
        self.assertIn("JavaScript", result)
        self.assertIn("BITS", result, "'BITS' must not become 'BIJavaScript'")

    def test_all_three_framework_name_compound_words(self):
        """A prompt with compound words for ALL three frameworks should
        protect all of them — 'ReactComponent', 'Nesting', 'BITS' all intact
        when mutating any framework."""
        prompt = "The ReactComponent uses nesting with BITS metrics."

        for framework in ["react", "nestjs", "typescript"]:
            with self.subTest(framework=framework):
                result = self.gen.mutate_context(prompt, framework=framework)

                # All three compound/longer words should remain intact
                self.assertIn(
                    "ReactComponent",
                    result,
                    f"'ReactComponent' should not be corrupted when mutating {framework}",
                )
                self.assertIn(
                    "nesting",
                    result.lower(),
                    f"'nesting' should not be corrupted when mutating {framework}",
                )
                self.assertIn(
                    "BITS", result, f"'BITS' should not be corrupted when mutating {framework}"
                )

    def test_no_framework_references_at_all(self):
        """A prompt with zero React/NestJS/TypeScript references should be
        returned unchanged regardless of which framework is requested."""
        prompt = "Write a Python script to parse CSV files."

        for framework in ["react", "nestjs", "typescript"]:
            with self.subTest(framework=framework):
                result = self.gen.mutate_context(prompt, framework=framework)
                self.assertEqual(
                    result,
                    prompt,
                    f"Prompt with no framework terms should be unchanged for {framework}",
                )


class TestGenerateVariantsIntegration(unittest.TestCase):
    """Integration tests for generate_variants() combining all three engines."""

    def test_generate_variants_produces_correct_count(self):
        """generate_variants(count=5) should yield 5 prompts including original."""
        gen = PromptGenerator(seed=42)
        base = GeneratedPrompt(
            category=PromptCategory.CODE,
            prompt=REACT_PROMPT,
            expected_keywords=["React", "component"],
            difficulty="medium",
        )

        variants = gen.generate_variants(base, count=5)

        self.assertEqual(len(variants), 5)
        self.assertEqual(variants[0].prompt, REACT_PROMPT)  # Original first

    def test_generate_variants_all_different(self):
        """Each variant should have a unique prompt text."""
        gen = PromptGenerator(seed=42)
        base = GeneratedPrompt(
            category=PromptCategory.CODE,
            prompt=REACT_PROMPT,
            expected_keywords=["React", "component"],
            difficulty="medium",
        )

        variants = gen.generate_variants(base, count=4)
        prompts = {v.prompt for v in variants}

        # With intensity increasing per variant, they should all be different
        self.assertEqual(len(prompts), 4)

    def test_generate_variants_preserves_metadata(self):
        """Variants should preserve category, keywords, and difficulty."""
        gen = PromptGenerator(seed=42)
        base = GeneratedPrompt(
            category=PromptCategory.DEBUGGING,
            prompt="Debug this code.",
            expected_keywords=["fix", "bug"],
            constraints={"no_markdown": True},
            difficulty="hard",
        )

        variants = gen.generate_variants(base, count=3)

        for v in variants:
            self.assertEqual(v.category, PromptCategory.DEBUGGING)
            self.assertEqual(v.expected_keywords, ["fix", "bug"])
            self.assertEqual(v.constraints, {"no_markdown": True})
            self.assertEqual(v.difficulty, "hard")

    def test_generate_variants_empty_techniques_list(self):
        """Empty techniques list should produce count-1 copies of original."""
        gen = PromptGenerator(seed=42)
        base = GeneratedPrompt(
            category=PromptCategory.CODE,
            prompt=REACT_PROMPT,
            expected_keywords=["React"],
            difficulty="medium",
        )

        variants = gen.generate_variants(base, count=4, techniques=[])

        self.assertEqual(len(variants), 4)
        for v in variants:
            self.assertEqual(v.prompt, REACT_PROMPT)


if __name__ == "__main__":
    unittest.main()
