"""unit test for wsdotroute module
"""
import unittest
import os
import re
from wsdotroute import create_event_feature_class
import arcpy


class TestWsdotRoute(unittest.TestCase):
    """Unit tests
    """

    def test_create_event_feature_class(self):
        # Create input event table
        scratch_gdb = arcpy.env.scratchGDB
        table_path = arcpy.CreateScratchName("Input", None, "Table", scratch_gdb)
        event_route_field = "RouteID"
        event_m_1_field = "BeginArm"
        event_m_2_field = "EndArm"
        route_layer_route_id_field = "RouteIdentifier"
        route_fc = os.path.join(os.path.split(__file__)[0], 'Sample.gdb', 'StateRouteLRS')
        out_fc = os.path.join(scratch_gdb, arcpy.CreateScratchName(
            "output", data_type="Feature Class", workspace=scratch_gdb))
        try:
            arcpy.management.CreateTable(*os.path.split(table_path))
            arcpy.management.AddField(table_path, event_route_field, field_type="TEXT",
                                      field_length=12)
            arcpy.management.AddField(
                table_path, event_m_1_field, field_type="DOUBLE")
            arcpy.management.AddField(
                table_path, event_m_2_field, field_type="DOUBLE")

            with arcpy.da.InsertCursor(table_path, (event_route_field, event_m_1_field,
                                                    event_m_2_field)) as cursor:
                cursor.insertRow(("005", 0, 5))

            out_fc = create_event_feature_class(
                table_path, route_fc, event_route_field, route_layer_route_id_field,
                event_m_1_field, event_m_2_field, out_fc=out_fc)

            # Test for expected output number of rows.
            get_count_output = arcpy.management.GetCount(out_fc)
            out_row_count = int(get_count_output[0])
            self.assertEqual(out_row_count, 1, "Output feature class should have 1 row.")
            del get_count_output, out_row_count

            with arcpy.da.SearchCursor(out_fc, ("EventOid", "SHAPE@")) as cursor:
                for oid, shape in cursor:
                    self.assertTrue(isinstance(oid, int),
                                    "OID should be an int")
                    self.assertTrue(isinstance(shape, arcpy.Polyline),
                                    "Geometry should be a Polyline")

        finally:
            if arcpy.Exists(table_path):
                arcpy.management.Delete(table_path)
            if out_fc and arcpy.Exists(out_fc):
                arcpy.management.Delete(out_fc)


if __name__ == '__main__':
    unittest.main()
