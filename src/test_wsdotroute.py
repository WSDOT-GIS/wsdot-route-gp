"""unit test for wsdot.route module
"""
from __future__ import (unicode_literals, print_function, division,
                        absolute_import)

import unittest
import os
import arcpy


class TestWsdotRoute(unittest.TestCase):
    """Unit tests
    """
    def test_create_event_feature_class(self):
        """Tests the ability to create an event feature class.
        """
        toolbox_path = None
        if 'wsdotroute' not in dir(arcpy):
            toolbox_path = os.path.join(
                os.path.split(__file__)[0], # script's directory
                "wsdot", "route", "esri", "toolboxes", "wsdotroute.pyt"
            )
            if not os.path.exists(toolbox_path):
                raise FileNotFoundError(toolbox_path)
            try:
                arcpy.ImportToolbox(toolbox_path)
            except OSError as ex:
                msg = 'Error loading toolbox "%s". File exists but could not be loaded.\n%s' % (toolbox_path, ex)
                self.fail(msg)
        # Create input event table
        # workspace = "in_memory"  # arcpy.env.scratchGDB
        workspace = arcpy.env.scratchGDB
        table_path = arcpy.CreateScratchName("Input", None, "Table", workspace)
        event_route_field = "RouteID"
        event_m_1_field = "BeginArm"
        event_m_2_field = "EndArm"
        route_layer_route_id_field = "RouteIdentifier"
        route_fc = os.path.join(os.path.split(
            __file__)[0], '..', 'Samples', 'Sample.gdb', 'StateRouteLRS')
        out_fc = arcpy.CreateScratchName(
            "output", data_type="Feature Class", workspace=workspace)
        data_rows = (
            ("005", 0, 5),
            ("I-5", 20, 100)
        )
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
                for row in data_rows:
                    cursor.insertRow(row)

            arcpy.wsdotroute.LocateRouteEvents(
                table_path, route_fc, event_route_field, route_layer_route_id_field,
                event_m_1_field, event_m_2_field, out_fc=out_fc)

            # out_fc = create_event_feature_class(
            #     table_path, route_fc, event_route_field, route_layer_route_id_field,
            #     event_m_1_field, event_m_2_field, out_fc=out_fc)

            # Test for expected output number of rows.
            get_count_output = arcpy.management.GetCount(out_fc)
            out_row_count = int(get_count_output[0])
            self.assertEqual(out_row_count, len(data_rows),
                             "Output feature class should have %d row(s)." % len(data_rows))
            del get_count_output, out_row_count

            with arcpy.da.SearchCursor(out_fc, ("EventOid", "SHAPE@", "Error")) as cursor:
                for oid, shape, error in cursor:
                    self.assertTrue(isinstance(oid, int),
                                    "OID should be an int")
                    self.assertTrue(isinstance(shape, arcpy.Polyline) or isinstance(error, str),
                                    "Geometry should be a Polyline")
                    if shape:
                        self.assertGreater(
                            shape.length, 0, "Length should be greater than 0")

        finally:
            if arcpy.Exists(table_path):
                arcpy.management.Delete(table_path)
            if out_fc and arcpy.Exists(out_fc):
                arcpy.management.Delete(out_fc)
            if toolbox_path:
                arcpy.RemoveToolbox(toolbox_path)


if __name__ == '__main__':
    unittest.main()
