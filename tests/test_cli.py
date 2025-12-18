"""
Tests for CLI functionality of trace_compactor
"""

import unittest
import sys
import io
import json
from unittest.mock import patch
from ctools.trace_compactor import _cli_main


class TestCLI(unittest.TestCase):
    """Test command-line interface"""

    def test_cli_stdin_basic(self):
        """Test CLI with stdin input"""
        test_input = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    x = 1/0
ZeroDivisionError: division by zero"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main(['--stdin'])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                self.assertIn("<COMPACT_PY_TRACEBACK", output)
                self.assertIn("ZeroDivisionError", output)

    def test_cli_stdin_with_project_root(self):
        """Test CLI with project root specified"""
        test_input = """Traceback (most recent call last):
  File "/home/user/myproject/main.py", line 10, in main
    process()
  File "/usr/lib/python3.11/json/decoder.py", line 100, in decode
    return loads(s)
ValueError: Invalid JSON"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--stdin',
                    '--project-root', '/home/user/myproject'
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                # Project file should be prioritized
                self.assertIn("main.py", output)

    def test_cli_stdin_with_max_frames(self):
        """Test CLI with custom max frames"""
        test_input = """Traceback (most recent call last):
  File "f1.py", line 1, in func1
    func2()
  File "f2.py", line 2, in func2
    func3()
  File "f3.py", line 3, in func3
    func4()
  File "f4.py", line 4, in func4
    raise ValueError("error")
ValueError: error"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--stdin',
                    '--max-frames', '2'
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                # Should limit frames
                frame_count = output.count("\n- ")
                self.assertLessEqual(frame_count, 2)

    def test_cli_json_output(self):
        """Test CLI with JSON output"""
        test_input = """Some text
Traceback (most recent call last):
  File "test.py", line 1, in <module>
    x = 1/0
ZeroDivisionError: division by zero"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--stdin',
                    '--json'
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)

                # Should be valid JSON
                try:
                    data = json.loads(output)
                    self.assertIn('original_preview', data)
                    self.assertIn('compacted_preview', data)
                    self.assertIn('frames_found', data)
                except json.JSONDecodeError:
                    self.fail("Output is not valid JSON")

    def test_cli_file_input(self):
        """Test CLI with file input"""
        test_content = """Traceback (most recent call last):
  File "test.py", line 1, in <module>
    raise RuntimeError("test")
RuntimeError: test"""

        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(test_content)
            temp_path = f.name

        try:
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--file', temp_path
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                self.assertIn("<COMPACT_PY_TRACEBACK", output)
                self.assertIn("RuntimeError", output)
        finally:
            import os
            os.unlink(temp_path)

    def test_cli_no_input_error(self):
        """Test CLI errors when no input method specified"""
        with patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as cm:
                _cli_main([])

            # Should exit with error
            self.assertNotEqual(cm.exception.code, 0)

    def test_cli_plain_text_unchanged(self):
        """Test that plain text without tracebacks passes through"""
        test_input = "This is just plain text without any Python tracebacks."

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main(['--stdin'])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                # Plain text should be unchanged
                self.assertEqual(output.strip(), test_input.strip())

    def test_cli_multiple_tracebacks(self):
        """Test CLI with multiple tracebacks in input"""
        test_input = """First error:
Traceback (most recent call last):
  File "test1.py", line 1, in <module>
    x = 1/0
ZeroDivisionError: division by zero

Second error:
Traceback (most recent call last):
  File "test2.py", line 1, in <module>
    y = {}['key']
KeyError: 'key'"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main(['--stdin'])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                # Should compact both
                compact_count = output.count("<COMPACT_PY_TRACEBACK")
                self.assertEqual(compact_count, 2)


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for CLI with realistic scenarios"""

    def test_cli_django_traceback(self):
        """Test with a Django-style traceback"""
        test_input = """Internal Server Error: /api/users/
Traceback (most recent call last):
  File "/usr/local/lib/python3.11/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
  File "/usr/local/lib/python3.11/site-packages/django/core/handlers/base.py", line 197, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
  File "/home/user/myapp/api/views.py", line 45, in user_list
    users = User.objects.filter(active=True)
  File "/home/user/myapp/api/models.py", line 20, in filter
    return self.get_queryset().filter(*args, **kwargs)
  File "/usr/local/lib/python3.11/site-packages/django/db/models/query.py", line 1000, in filter
    return self._filter_or_exclude(False, *args, **kwargs)
AttributeError: 'NoneType' object has no attribute 'filter'"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--stdin',
                    '--project-root', '/home/user/myapp',
                    '--max-frames', '3'
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                # Should prioritize user's code
                self.assertIn("views.py", output)
                self.assertIn("models.py", output)
                # Should be much shorter
                self.assertLess(len(output), len(test_input))

    def test_cli_pytest_failure(self):
        """Test with pytest-style traceback"""
        test_input = """============================= FAILURES ==============================
__________________________ test_user_creation __________________________

    def test_user_creation():
>       user = create_user(name=None)
E       Traceback (most recent call last):
E         File "/home/user/myapp/tests/test_users.py", line 10, in test_user_creation
E           user = create_user(name=None)
E         File "/home/user/myapp/users/factory.py", line 25, in create_user
E           validate_name(name)
E         File "/home/user/myapp/users/validators.py", line 5, in validate_name
E           if len(name) == 0:
E       TypeError: object of type 'NoneType' has no len()

tests/test_users.py:10: TypeError"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--stdin',
                    '--project-root', '/home/user/myapp'
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                # Should preserve test context and compact traceback
                self.assertIn("test_user_creation", output)

    def test_cli_async_traceback(self):
        """Test with async/await traceback"""
        test_input = """Traceback (most recent call last):
  File "main.py", line 20, in <module>
    asyncio.run(main())
  File "/usr/lib/python3.11/asyncio/runners.py", line 190, in run
    return runner.run(main)
  File "/home/user/app/handlers.py", line 50, in handle_request
    result = await process_data(data)
  File "/home/user/app/processor.py", line 30, in process_data
    return await fetch_from_db(data['id'])
KeyError: 'id'"""

        with patch('sys.stdin', io.StringIO(test_input)):
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                exit_code = _cli_main([
                    '--stdin',
                    '--project-root', '/home/user/app'
                ])

                output = mock_stdout.getvalue()
                self.assertEqual(exit_code, 0)
                self.assertIn("handlers.py", output)
                self.assertIn("processor.py", output)
                self.assertIn("KeyError", output)


if __name__ == "__main__":
    unittest.main()
