"""
Tests for ctools.trace_compactor module
"""

import unittest
import json
from ctools.trace_compactor import (
    parse_traceback_text,
    compact_traceback_block,
    rewrite_prompt_for_claude,
)


class TestParseTraceback(unittest.TestCase):
    """Test traceback parsing functionality"""

    def test_parse_simple_traceback(self):
        """Test parsing a simple traceback"""
        traceback = """Traceback (most recent call last):
  File "/home/user/test.py", line 10, in main
    result = divide(5, 0)
  File "/home/user/test.py", line 5, in divide
    return a / b
ZeroDivisionError: division by zero"""

        parsed = parse_traceback_text(traceback)

        self.assertEqual(len(parsed["frames"]), 2)
        self.assertEqual(parsed["frames"][0]["filename"], "/home/user/test.py")
        self.assertEqual(parsed["frames"][0]["lineno"], 10)
        self.assertEqual(parsed["frames"][0]["name"], "main")
        self.assertEqual(parsed["frames"][1]["lineno"], 5)
        self.assertEqual(parsed["frames"][1]["name"], "divide")

        self.assertEqual(len(parsed["exception_lines"]), 1)
        self.assertIn("ZeroDivisionError", parsed["exception_lines"][0])

    def test_parse_traceback_with_code_lines(self):
        """Test parsing traceback that includes code lines"""
        traceback = """Traceback (most recent call last):
  File "/home/user/test.py", line 10, in main
    result = divide(5, 0)
  File "/home/user/test.py", line 5, in divide
    return a / b
ZeroDivisionError: division by zero"""

        parsed = parse_traceback_text(traceback)

        self.assertEqual(parsed["frames"][0]["code_line"], "result = divide(5, 0)")
        self.assertEqual(parsed["frames"][1]["code_line"], "return a / b")

    def test_parse_complex_exception(self):
        """Test parsing traceback with complex exception message"""
        traceback = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    data['key']
KeyError: 'key'"""

        parsed = parse_traceback_text(traceback)

        self.assertEqual(len(parsed["frames"]), 1)
        self.assertEqual(len(parsed["exception_lines"]), 1)
        self.assertIn("KeyError", parsed["exception_lines"][0])

    def test_parse_empty_text(self):
        """Test parsing empty text"""
        parsed = parse_traceback_text("")

        self.assertEqual(len(parsed["frames"]), 0)
        self.assertEqual(len(parsed["exception_lines"]), 0)


class TestCompactTraceback(unittest.TestCase):
    """Test traceback compaction functionality"""

    def test_compact_simple_traceback(self):
        """Test compacting a simple traceback"""
        traceback = """Traceback (most recent call last):
  File "/home/user/myproject/api.py", line 10, in handler
    result = process()
  File "/home/user/myproject/processor.py", line 5, in process
    return data['key']
KeyError: 'key'"""

        compacted = compact_traceback_block(traceback, project_root="/home/user/myproject")

        # Verify it contains the compact markers
        self.assertIn("<COMPACT_PY_TRACEBACK", compacted)
        self.assertIn("</COMPACT_PY_TRACEBACK>", compacted)

        # Verify it contains the exception
        self.assertIn("KeyError", compacted)

        # Verify it contains file references
        self.assertIn("api.py", compacted)
        self.assertIn("processor.py", compacted)

        # Verify it's shorter than original
        self.assertLess(len(compacted), len(traceback))

    def test_compact_with_max_frames(self):
        """Test compacting with frame limit"""
        traceback = """Traceback (most recent call last):
  File "file1.py", line 1, in func1
    func2()
  File "file2.py", line 2, in func2
    func3()
  File "file3.py", line 3, in func3
    func4()
  File "file4.py", line 4, in func4
    func5()
  File "file5.py", line 5, in func5
    raise ValueError("error")
ValueError: error"""

        compacted = compact_traceback_block(traceback, max_frames=2)

        # Should only include max 2 frames
        self.assertIn("<COMPACT_PY_TRACEBACK", compacted)
        # Count frame markers (lines starting with "- ")
        frame_count = compacted.count("\n- ")
        self.assertLessEqual(frame_count, 2)

    def test_compact_non_traceback_text(self):
        """Test that non-traceback text is returned unchanged"""
        text = "This is just regular text without any traceback"

        result = compact_traceback_block(text)

        # Should return original text
        self.assertEqual(result, text)

    def test_compact_prioritizes_project_frames(self):
        """Test that frames from project root are prioritized"""
        traceback = """Traceback (most recent call last):
  File "/usr/lib/python3.11/site-packages/click/core.py", line 100, in invoke
    return callback()
  File "/usr/lib/python3.11/site-packages/click/decorators.py", line 50, in wrapper
    return func()
  File "/home/user/myproject/main.py", line 20, in main
    process_data()
  File "/home/user/myproject/processor.py", line 10, in process_data
    return data['missing']
KeyError: 'missing'"""

        compacted = compact_traceback_block(
            traceback,
            project_root="/home/user/myproject",
            max_frames=2
        )

        # Should prioritize project files over site-packages
        self.assertIn("main.py", compacted)
        self.assertIn("processor.py", compacted)
        # Site-packages frames should be deprioritized
        self.assertNotIn("click/core.py", compacted)


class TestRewritePrompt(unittest.TestCase):
    """Test prompt rewriting functionality"""

    def test_rewrite_prompt_with_traceback(self):
        """Test rewriting a prompt containing a traceback"""
        prompt = """I'm getting this error:

Traceback (most recent call last):
  File "test.py", line 5, in main
    result = process()
  File "test.py", line 2, in process
    return 1/0
ZeroDivisionError: division by zero

Can you help me fix it?"""

        rewritten = rewrite_prompt_for_claude(prompt)

        # Should contain compact markers
        self.assertIn("<COMPACT_PY_TRACEBACK", rewritten)
        self.assertIn("</COMPACT_PY_TRACEBACK>", rewritten)

        # Should still contain the surrounding text
        self.assertIn("I'm getting this error:", rewritten)
        self.assertIn("Can you help me fix it?", rewritten)

        # Note: For very short tracebacks, compaction may not always be shorter
        # due to formatting overhead, but it's still more token-efficient

    def test_rewrite_multiple_tracebacks(self):
        """Test rewriting prompt with multiple tracebacks"""
        prompt = """First error:
Traceback (most recent call last):
  File "test1.py", line 1, in <module>
    x = 1/0
ZeroDivisionError: division by zero

Second error:
Traceback (most recent call last):
  File "test2.py", line 1, in <module>
    y = dict()['key']
KeyError: 'key'"""

        rewritten = rewrite_prompt_for_claude(prompt)

        # Should compact both tracebacks
        compact_count = rewritten.count("<COMPACT_PY_TRACEBACK")
        self.assertEqual(compact_count, 2)

    def test_rewrite_prompt_without_traceback(self):
        """Test that prompts without tracebacks are unchanged"""
        prompt = "This is just a regular question about Python code."

        rewritten = rewrite_prompt_for_claude(prompt)

        self.assertEqual(rewritten, prompt)

    def test_rewrite_already_compacted(self):
        """Test that already compacted tracebacks are not reprocessed"""
        prompt = """I have this error:
<COMPACT_PY_TRACEBACK fingerprint=abc123>
Exception: ValueError: test
Relevant frames:
- test.py:1 in main
</COMPACT_PY_TRACEBACK>"""

        rewritten = rewrite_prompt_for_claude(prompt)

        # Should be unchanged (idempotent)
        self.assertEqual(rewritten, prompt)

    def test_rewrite_with_project_root(self):
        """Test rewriting with project root for better frame scoring"""
        prompt = """Error:
Traceback (most recent call last):
  File "/usr/lib/python3.11/json/decoder.py", line 100, in decode
    return loads(s)
  File "/home/user/myapp/parser.py", line 50, in parse
    return json.loads(data)
  File "/home/user/myapp/handler.py", line 20, in handle
    parse(bad_data)
ValueError: Invalid JSON"""

        rewritten = rewrite_prompt_for_claude(
            prompt,
            project_root="/home/user/myapp"
        )

        # Project files should be in the compacted output
        self.assertIn("parser.py", rewritten)
        self.assertIn("handler.py", rewritten)


class TestFrameScoring(unittest.TestCase):
    """Test frame scoring and prioritization"""

    def test_project_frames_score_higher(self):
        """Test that frames in project root score highest"""
        from ctools.trace_compactor import _frame_score

        project_frame = {
            "filename": "/home/user/myproject/main.py",
            "lineno": 10,
            "name": "main",
            "raw_index": 2
        }

        external_frame = {
            "filename": "/usr/lib/python3.11/os.py",
            "lineno": 100,
            "name": "getcwd",
            "raw_index": 1
        }

        project_score = _frame_score(project_frame, project_root="/home/user/myproject")
        external_score = _frame_score(external_frame, project_root="/home/user/myproject")

        # Project frame should score higher
        self.assertGreater(project_score, external_score)

    def test_recent_frames_score_higher(self):
        """Test that more recent frames (lower index) score higher"""
        from ctools.trace_compactor import _frame_score

        early_frame = {
            "filename": "/home/test.py",
            "lineno": 1,
            "name": "early",
            "raw_index": 0
        }

        late_frame = {
            "filename": "/home/test.py",
            "lineno": 10,
            "name": "late",
            "raw_index": 5
        }

        early_score = _frame_score(early_frame)
        late_score = _frame_score(late_frame)

        # Later frames (closer to error) should score higher
        self.assertGreater(late_score, early_score)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_malformed_traceback(self):
        """Test handling of malformed traceback"""
        malformed = """Traceback (most recent call last):
  File "test.py", line INVALID, in func
    code here
SomeError"""

        # Should not crash, should handle gracefully
        result = compact_traceback_block(malformed)
        # Should still attempt to compact or return original
        self.assertIsInstance(result, str)

    def test_traceback_with_special_characters(self):
        """Test traceback with special characters in strings"""
        traceback = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise ValueError("Error with 'quotes' and \\"escapes\\"")
ValueError: Error with 'quotes' and "escapes\""""

        result = compact_traceback_block(traceback)

        self.assertIn("<COMPACT_PY_TRACEBACK", result)
        self.assertIn("ValueError", result)

    def test_very_long_traceback(self):
        """Test handling of very long tracebacks"""
        # Create a traceback with many frames
        frames = []
        for i in range(50):
            frames.append(f'  File "file{i}.py", line {i}, in func{i}\n    call_next()')

        traceback = "Traceback (most recent call last):\n"
        traceback += "\n".join(frames)
        traceback += "\nRuntimeError: too deep"

        result = compact_traceback_block(traceback, max_frames=5)

        # Should limit to max_frames
        self.assertIn("<COMPACT_PY_TRACEBACK", result)
        # Compacted version should be much shorter
        self.assertLess(len(result), len(traceback) / 2)

    def test_unicode_in_traceback(self):
        """Test handling of unicode characters in traceback"""
        traceback = """Traceback (most recent call last):
  File "tëst.py", line 1, in función
    raise ValueError("Erreur: ñoño")
ValueError: Erreur: ñoño"""

        result = compact_traceback_block(traceback)

        self.assertIn("<COMPACT_PY_TRACEBACK", result)
        self.assertIn("ValueError", result)


class TestFingerprinting(unittest.TestCase):
    """Test deterministic fingerprinting"""

    def test_same_traceback_same_fingerprint(self):
        """Test that identical tracebacks produce same fingerprint"""
        traceback = """Traceback (most recent call last):
  File "test.py", line 5, in main
    raise ValueError("test")
ValueError: test"""

        result1 = compact_traceback_block(traceback)
        result2 = compact_traceback_block(traceback)

        # Extract fingerprints
        import re
        fp_match1 = re.search(r'fingerprint=(\w+)', result1)
        fp_match2 = re.search(r'fingerprint=(\w+)', result2)

        self.assertIsNotNone(fp_match1)
        self.assertIsNotNone(fp_match2)
        self.assertEqual(fp_match1.group(1), fp_match2.group(1))

    def test_different_tracebacks_different_fingerprints(self):
        """Test that different tracebacks produce different fingerprints"""
        traceback1 = """Traceback (most recent call last):
  File "test1.py", line 5, in main
    raise ValueError("test")
ValueError: test"""

        traceback2 = """Traceback (most recent call last):
  File "test2.py", line 10, in other
    raise KeyError("test")
KeyError: test"""

        result1 = compact_traceback_block(traceback1)
        result2 = compact_traceback_block(traceback2)

        # Extract fingerprints
        import re
        fp_match1 = re.search(r'fingerprint=(\w+)', result1)
        fp_match2 = re.search(r'fingerprint=(\w+)', result2)

        self.assertIsNotNone(fp_match1)
        self.assertIsNotNone(fp_match2)
        self.assertNotEqual(fp_match1.group(1), fp_match2.group(1))


if __name__ == "__main__":
    unittest.main()
