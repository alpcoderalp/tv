import sys
import unittest
import os
import pathlib

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.chdir(pathlib.Path(__file__).parent)

# Discover and run tests in current directory
loader = unittest.TestLoader()
suite = unittest.TestSuite()

import test_strict_terminal_fix
import test_quantize_verify_fix
import test_end_to_end_lifecycle

suite.addTests(loader.loadTestsFromModule(test_strict_terminal_fix))
suite.addTests(loader.loadTestsFromModule(test_quantize_verify_fix))
suite.addTests(loader.loadTestsFromModule(test_end_to_end_lifecycle))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

print("\n" + "=" * 80)
print(f"CANDIDATE TEST SUMMARY: Ran {result.testsRun} tests.")
print(f"Errors: {len(result.errors)}, Failures: {len(result.failures)}")
if result.wasSuccessful():
    print("ALL TESTS PASSED SUCCESSFULLY! (100% PASS)")
    sys.exit(0)
else:
    print("TESTS FAILED!")
    sys.exit(1)

