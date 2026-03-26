
import unittest
import json
import sys
from unittest.mock import MagicMock

# Add the parent directory to the Python path to allow importing Os_Toolkit
sys.path.append('..')

from Os_Toolkit import ForensicOSToolkit, SixW1H

class TestOsToolkitRefactor(unittest.TestCase):

    def setUp(self):
        """Set up a mock ForensicOSToolkit instance for testing."""
        self.toolkit = ForensicOSToolkit()
        # Mock the logger to prevent console output during tests
        self.toolkit.logger = MagicMock()
        # Provide a sample taxonomy that mimics the structure used by the tool
        self.toolkit.taxonomy = {
            "core_hierarchy": {
                "system": "The foundational layer of the operating system."
            },
            "domain_technical": {
                "hardware_cpu": "Central Processing Unit - the brain of the computer."
            },
            "extraction_entities": {
                "user_account": "An account for a user to interact with the system."
            }
        }

    def test_generate_6w1h_finds_why_in_technical_domain(self):
        """
        Verify that the refactored _generate_6w1h function can find a 'why'
        description in the 'domain_technical' section of the taxonomy.
        This specifically tests the fix for the 'cpu_3' node issue.
        """
        what = "cpu_3"
        category = "hardware_cpu"

        # Call the private method directly to test its logic
        sixw1h_result = self.toolkit._generate_6w1h(what, category)

        # Assert that the 'why' field was correctly populated
        expected_why = "Central Processing Unit - the brain of the computer."
        self.assertEqual(sixw1h_result.why, expected_why)

    def test_generate_6w1h_finds_why_in_core_hierarchy(self):
        """
        Verify that the function can find a 'why' description in the
        'core_hierarchy' section.
        """
        what = "kernel_task"
        category = "system"
        sixw1h_result = self.toolkit._generate_6w1h(what, category)
        expected_why = "The foundational layer of the operating system."
        self.assertEqual(sixw1h_result.why, expected_why)

    def test_generate_6w1h_returns_empty_why_for_unknown_category(self):
        """
        Verify that the function returns an empty 'why' string when the
        category does not match any key in the taxonomy.
        """
        what = "unknown_item"
        category = "non_existent_category"
        sixw1h_result = self.toolkit._generate_6w1h(what, category)
        self.assertEqual(sixw1h_result.why, "")

if __name__ == '__main__':
    # Note: Running this file directly might fail if 'Os Toolkit.py' is not in the parent directory.
    # It is intended to be run from a test runner at the project root.
    unittest.main()
