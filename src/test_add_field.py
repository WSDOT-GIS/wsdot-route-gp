from __future__ import unicode_literals, print_function, division, absolute_import

from os.path import split
import unittest
from wsdotroute import add_standardized_route_id_field, RouteIdSuffixType
import arcpy

class TestAddField(unittest.TestCase):
    """Unit tests
    """
    def test_add_route_id_field(self):
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
            workspace, table_name = split(table_path)
            arcpy.management.CreateTable(workspace, table_name)
            arcpy.management.AddFields(table_path, [
                [field_names[0], "TEXT", None, 11],
                [field_names[1], "TEXT", None, None]
            ])

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
