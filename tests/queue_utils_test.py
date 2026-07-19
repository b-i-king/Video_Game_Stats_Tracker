import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeCursor:
    def __init__(self):
        self.query = ""
        self.parameters = ()
        self.rowcount = 2

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def execute(self, query, parameters):
        self.query = " ".join(query.split())
        self.parameters = parameters


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def load_queue_utils():
    psycopg2 = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extras.RealDictCursor = object
    psycopg2.connect = lambda **kwargs: None
    psycopg2.extras = extras
    with patch.dict(
        sys.modules,
        {"psycopg2": psycopg2, "psycopg2.extras": extras},
    ):
        return importlib.import_module("utils.queue_utils")


queue_utils = load_queue_utils()


class QueueUtilsTest(unittest.TestCase):
    def test_reset_stale_processing_uses_parameterized_interval(self):
        connection = FakeConnection()

        with patch.object(queue_utils, "_get_conn", return_value=connection):
            count = queue_utils.reset_stale_processing(15)

        self.assertEqual(count, 2)
        self.assertIn("(%s * INTERVAL '1 minute')", connection.cursor_instance.query)
        self.assertEqual(connection.cursor_instance.parameters, (15,))
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_purge_old_sent_uses_parameterized_interval(self):
        connection = FakeConnection()

        with patch.object(queue_utils, "_get_conn", return_value=connection):
            count = queue_utils.purge_old_sent(30)

        self.assertEqual(count, 2)
        self.assertIn("(%s * INTERVAL '1 day')", connection.cursor_instance.query)
        self.assertEqual(connection.cursor_instance.parameters, (30,))
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
