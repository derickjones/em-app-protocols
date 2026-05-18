import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from gemini_search_service import GeminiSearchService


class GeminiSearchServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = GeminiSearchService()

    def test_extract_text_delta_handles_cumulative_snapshots(self):
        first_payload = {
            "candidates": [{"content": {"parts": [{"text": "Bottom Line: Give IM epinephrine"}]}}]
        }
        second_payload = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Bottom Line: Give IM epinephrine\n\n| Drug | Dose |"}]
                }
            }]
        }

        first_delta, previous_text = self.service._extract_text_delta(first_payload, "")
        second_delta, previous_text = self.service._extract_text_delta(second_payload, previous_text)

        self.assertEqual(first_delta, "Bottom Line: Give IM epinephrine")
        self.assertEqual(second_delta, "\n\n| Drug | Dose |")
        self.assertEqual(previous_text, "Bottom Line: Give IM epinephrine\n\n| Drug | Dose |")


if __name__ == "__main__":
    unittest.main()