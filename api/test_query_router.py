import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from query_router import route_query


class QueryRouterTests(unittest.TestCase):
    def test_local_protocol_queries(self):
        self.assertEqual(route_query("What is our sepsis protocol?"), "local_protocol")
        self.assertEqual(route_query("Use our protocol for DKA."), "local_protocol")
        self.assertEqual(route_query("What does our bundle say about stroke?"), "local_protocol")
        self.assertEqual(route_query("What does my asthma protocol say?"), "local_protocol")
        self.assertEqual(route_query("What does the asthma protocol say?"), "local_protocol")

    def test_personal_queries(self):
        self.assertEqual(route_query("Use my uploaded bronchiolitis note."), "personal")
        self.assertEqual(route_query("Answer from my personal materials about RSV."), "personal")
        self.assertEqual(route_query("Summarize my references on pediatric asthma."), "personal")
        self.assertEqual(route_query("Summarize my uploaded asthma protocol PDF."), "personal")

    def test_general_clinical_queries(self):
        self.assertEqual(route_query("How do I manage hyperkalemia with ECG changes?"), "general_clinical")
        self.assertEqual(route_query("What is the first-line treatment for status epilepticus?"), "general_clinical")


if __name__ == "__main__":
    unittest.main()