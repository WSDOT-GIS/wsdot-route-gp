"""Defines test for the module functions.
"""

from __future__ import print_function, division, unicode_literals, absolute_import
import unittest
import os

# arcpy is only available as part of the ArcGIS software and is not via pip
# or other package managers.

try:
    import arcpy
except ImportError:
    # If arcpy cannot be imported, create an arcpy parameter
    # and set it to None. In tests requiring arcpy, check
    # to see if arcpy is truthy, and if it isn't, skip the test.
    arcpy = None
else:
    # These modules require arcpy, so we'll only import them
    # if arcpy is available.
    from wsdotroute import (add_standardized_route_id_field,
                            copy_with_segment_ids,
                            points_to_line_event_features,
                            standardize_route_id, RouteIdSuffixType)

class ModuleTest(unittest.TestCase):
    """Defines unit test test case.
    """

    def skip_if_no_arcpy(self):
        """Skips the current test if arcpy is not installed.
        Returns True if skipTest is called, False otherwise.
        """
        if not arcpy:
            self.skipTest("arcpy module not installed.")
            return True
        return False

    def test_route_id_parsing(self):
        """Tests the route id parsing function.
        This will still run even if arcpy is not available.
        """
        in_id = "I-5"
        expected_out = "005i"
        actual_out = standardize_route_id(
            in_id, RouteIdSuffixType.has_i_suffix | RouteIdSuffixType.has_d_suffix)
        self.assertEqual(expected_out, actual_out)
        # Test default parameters, which should be the same as above
        actual_out = standardize_route_id(in_id)
        self.assertEqual(expected_out, actual_out)

    def test_create_segment_id_table(self):
        """Tests the copy_with_segment_ids function.
        """
        if self.skip_if_no_arcpy():
            return

        samples_path = os.path.join(os.path.dirname(__file__), "../Samples")
        input_layer = os.path.join(samples_path, "CrabBeginAndEndPoints.lyr")
        output_fc = arcpy.CreateScratchName(workspace="in_memory")
        try:
            row_count, segment_count = copy_with_segment_ids(
                input_layer, output_fc)
            self.assertTrue(arcpy.Exists(output_fc))
            self.assertEqual(row_count / 2, segment_count)
        finally:
            arcpy.management.Delete(output_fc)

    def test_points_to_line_events(self):
        """Tests the points_to_line_events function
        """
        if self.skip_if_no_arcpy():
            return

        try:
            samples_path = os.path.join(
                os.path.dirname(__file__), "../Samples")
            input_layer = os.path.join(
                samples_path, "CrabBeginAndEndPoints.lyr")
            routes_layer = os.path.join(samples_path, "CrabRoutes.lyr")
            out_table = arcpy.CreateScratchName(workspace="in_memory")
            points_to_line_event_features(input_layer, routes_layer,
                                          "RouteID", "50 FEET", out_table)
            self.assertTrue(arcpy.Exists(out_table))

            null_geometry_detected, null_rid, null_m, null_m2 = (False,) * 4
            # Assertions per row
            with arcpy.da.SearchCursor(out_table, ("SHAPE@", "RID", "Measure", "EndMeasure")) as cursor:
                for (shape, rid, measure, end_measure) in cursor:
                    if not shape:
                        null_geometry_detected = True
                    if not rid:
                        null_rid = True
                    if measure is None:
                        null_m = True
                    if end_measure is None:
                        null_m2 = True
                    if null_geometry_detected and null_rid and null_m and null_m2:
                        break
            self.assertFalse(null_geometry_detected, "The output feature class should not contain null geometry.")
            self.assertFalse(null_rid, "Should not contain null RID values")
            self.assertFalse(null_m, "No measures should be null")
            self.assertFalse(null_m2, "No end measures should be null")
        finally:
            if out_table and arcpy.Exists(out_table):
                arcpy.management.Delete(out_table)

    def test_add_route_id_field(self):
        """Tests the add_route_id_field function.
        """
        if self.skip_if_no_arcpy():
            return

        sample_data = [
            ["I-5", "d"],
            ["005", "i"]
        ]
        expected_output = [
            ["I-5", "d", "005d", None],
            ["005", "i", "005i", None]
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
                arcpy.management.AddField(
                    table_path, field_names[0], "TEXT", field_length=11)
                arcpy.management.AddField(table_path, field_names[1], "TEXT")

            # Populate the new table.
            with arcpy.da.InsertCursor(table_path, field_names[0:2]) as cursor:
                for row in sample_data:
                    cursor.insertRow(row)

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
