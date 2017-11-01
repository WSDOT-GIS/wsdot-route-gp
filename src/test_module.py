"""Defines test for the module functions.
"""

from __future__ import print_function, division, unicode_literals, absolute_import
import unittest
import os
try:
    import arcpy
except ImportError:
    arcpy = None
else:
    from wsdotroute import (add_standardized_route_id_field,
                            copy_with_segment_ids,
                            points_to_line_events, RouteIdSuffixType,
                            standardize_route_id)


class ModuleTest(unittest.TestCase):
    def test_route_id_parsing(self):
        in_id = "I-5"
        expected_out = "005i"
        actual_out = standardize_route_id(
            in_id, RouteIdSuffixType.has_i_suffix | RouteIdSuffixType.has_d_suffix)
        self.assertEqual(expected_out, actual_out)
        # Test default parameters, which should be the same as above
        actual_out = standardize_route_id(in_id)
        self.assertEqual(expected_out, actual_out)
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

    def test_points_to_line_events(self):
        if not arcpy:
            self.skipTest("arcpy module not installed.")
            return

        samples_path = os.path.join(os.path.dirname(__file__), "../Samples")
        input_layer = os.path.join(samples_path, "CrabBeginAndEndPoints.lyr")
        routes_layer = os.path.join(samples_path, "CrabRoutes.lyr")
        out_table = arcpy.CreateScratchName(workspace="in_memory")
        points_to_line_events(input_layer, routes_layer,
                              "RouteID", "50 FEET", out_table)

    def test_add_route_id_field(self):
        if not arcpy:
            self.skipTest("arcpy module not installed.")
            return

        sample_data = [
            ["I-5", "d"],
            ["005", "i"]
        ]
        expected_output = [
            ["I-5", "d", "005d", None],
            ["005", "i", "005", None]
        ]

        field_names = ("RouteID", "Direction", "MergedRouteId", "Error")

        # Create table
        table_path = arcpy.CreateScratchName(workspace="in_memory")
        try:
            # Create sample table
            workspace, table_name = os.path.split(table_path)
            arcpy.management.CreateTable(workspace, table_name)
            try:
                arcpy.management.AddFields(table_path, [
                    [field_names[0], "TEXT", None, 11],
                    [field_names[1], "TEXT", None, None]
                ])
            except AttributeError:
                arcpy.management.AddField(table_path, field_names[0], "TEXT", field_length=11)
                arcpy.management.AddField(table_path, field_names[1], "TEXT")

            # Call funciton to add field
            add_standardized_route_id_field(
                table_path,
                *(field_names + (RouteIdSuffixType.has_both_i_and_d,)))

            # Check the values
            with arcpy.da.SearchCursor(table_path, field_names) as cursor:
                row_count = 0
                for row in cursor:
                    expected_row = expected_output[row_count]
                    for i in range(0, len(expected_row)):
                        self.assertEqual(row[i], expected_row[i])
                    row_count += 1
        finally:
            if arcpy.Exists(table_path):
                arcpy.management.Delete(table_path)


if __name__ == '__main__':
    unittest.main()
