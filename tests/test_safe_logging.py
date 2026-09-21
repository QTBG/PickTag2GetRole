import io
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from safe_logging import ApplicationLogFilter, PrivacyFormatter, configure_logging


class PrivacyLoggingTests(unittest.TestCase):
    def test_library_payloads_never_reach_handler_even_at_error_level(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(ApplicationLogFilter())
        handler.setFormatter(PrivacyFormatter('%(message)s'))
        for name in ('discord.gateway', 'discord.http', 'asyncio', 'root', 'PickTag2GetRoleFake'):
            handler.handle(logging.LogRecord(name, logging.ERROR, '', 0,
                'private profile and token: %s', ('sensitive-payload',), None))
        handler.handle(logging.LogRecord('PickTag2GetRole.Database', logging.INFO, '', 0,
            'Database backup completed', (), None))
        self.assertEqual(stream.getvalue(), 'Database backup completed\n')

    def test_exception_and_stack_payloads_are_discarded(self):
        try:
            raise ValueError('username, Discord identifier, or HTTP response')
        except ValueError:
            import sys
            record = logging.LogRecord('PickTag2GetRole', logging.ERROR, '', 0,
                'Application command failed', (), sys.exc_info(),
                sinfo='private stack details')
        record.exc_text = 'a cached traceback with secret values'
        self.assertEqual(PrivacyFormatter('%(message)s').format(record),
                         'Application command failed')
        self.assertIsNotNone(record.exc_info)

    def test_stdout_and_rotating_file_both_filter_payloads(self):
        root = logging.getLogger()
        old_handlers, old_level = root.handlers[:], root.level
        # basicConfig(force=True) closes installed handlers; detach test runner ones.
        root.handlers = []
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'audit.log'
                stream = io.StringIO()
                with patch('sys.stderr', stream):
                    configure_logging('DEBUG', str(path))
                    logging.getLogger('discord.gateway').debug('secret-profile')
                    logging.getLogger('discord.http').error('secret-api-body')
                    logging.getLogger('PickTag2GetRole').info('Application logging initialized')
                for handler in root.handlers:
                    handler.flush()
                    handler.close()
                file_text = path.read_text(encoding='utf-8')
                for text in (file_text, stream.getvalue()):
                    self.assertIn('Application logging initialized', text)
                    self.assertNotIn('secret', text)
        finally:
            root.handlers = old_handlers
            root.setLevel(old_level)


if __name__ == '__main__':
    unittest.main()
