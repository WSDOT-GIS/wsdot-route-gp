"""Defines test for the module functions.
"""

from __future__ import print_function, division, unicode_literals, absolute_import
import unittest
import os
from wsdotroute import create_segment_id_table

class ModuleTest(unittest.TestCase):
    def test_create_segment_id_table(self):
        samples_path = os.path.join(os.path.dirname(__file__), "../Samples")
        input_layer = os.path.join(samples_path, "CrabBeginAndEndPoints.lyr")
        narray = create_segment_id_table(input_layer)
        print(narray)
        self.assertIsNotNone(narray)

if __name__ == '__main__':
    unittest.main()
