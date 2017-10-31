"""Defines test for the module functions.
"""

from __future__ import print_function, division, unicode_literals, absolute_import
import unittest
import os
import arcpy
from wsdotroute import copy_with_segment_ids

class ModuleTest(unittest.TestCase):
    def test_create_segment_id_table(self):
        samples_path = os.path.join(os.path.dirname(__file__), "../Samples")
        input_layer = os.path.join(samples_path, "CrabBeginAndEndPoints.lyr")
        output_fc = arcpy.CreateScratchName(workspace="in_memory")
        try:
            row_count, segment_count = copy_with_segment_ids(input_layer, output_fc)
            self.assertTrue(arcpy.Exists(output_fc))
            self.assertEqual(row_count / 2, segment_count)
        finally:
            arcpy.management.Delete(output_fc)

if __name__ == '__main__':
    unittest.main()
