#!/usr/bin/env python
"""
Скрипт для запуска тестов recommendation-service.
Использование аналогично Django: python run_tests.py
(вместо python manage.py test для Django-проектов).
"""
import sys
import unittest


def main():
    loader = unittest.TestLoader()
    suite = loader.discover(".", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
