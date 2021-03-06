"""Allows user to locate points or route segments along WA routes.
"""
from __future__ import (unicode_literals, print_function, division,
                        absolute_import)

import re
from os.path import split as split_path, join as join_path
import arcpy
from .route_ids import RouteIdSuffixType, standardize_route_id
try:
    from arcpy.da import Describe
except ImportError:
    from arcpy import Describe


def _get_row_count(view):
    return int(arcpy.management.GetCount(view)[0])


def add_standardized_route_id_field(in_table, route_id_field, direction_field, out_field_name, out_error_field_name, route_id_suffix_type, wsdot_validation=True):
    """Adds route ID + direction field to event table that has both unsuffixed route ID and direction fields.
    """
    # Make sure an output route ID suffix type other than "unsuffixed" has been specified.
    if route_id_suffix_type == RouteIdSuffixType.has_no_suffix:
        raise ValueError("Invalid route ID suffix type: %s" %
                         route_id_suffix_type)

    if wsdot_validation:
        # Determine the length of the output route ID field based on route suffix type
        out_field_length = 11
        if route_id_suffix_type == RouteIdSuffixType.has_i_suffix or route_id_suffix_type == RouteIdSuffixType.has_d_suffix:
            out_field_length += 1
        elif route_id_suffix_type == RouteIdSuffixType.has_both_i_and_d:
            out_field_length += 2
    else:
        # TODO: Get field length from arcpy.ListFields(in_table) using route_id_field's length + 2.
        out_field_length = None

    # Add new fields to the output table.
    if "AddFields" in dir(arcpy.management):
        arcpy.management.AddFields(in_table, [
            [out_field_name, "TEXT", None, out_field_length, None],
            # Use default length (255)
            [out_error_field_name, "TEXT", None, None]
        ])
    else:
        # ArcGIS Desktop 10.5.1 doesn't have AddFields, so use multiple AddField calls.
        arcpy.management.AddField(
            in_table, out_field_name, "TEXT", field_length=out_field_length)
        arcpy.management.AddField(in_table, out_error_field_name, "TEXT")

    decrease_re = re.compile(r"^d", re.IGNORECASE)

    with arcpy.da.UpdateCursor(in_table, (route_id_field, direction_field, out_field_name, out_error_field_name)) as cursor:
        for row in cursor:
            rid = row[0]
            direction = row[1]
            if rid:
                # Get unsuffixed, standardized route ID.
                try:
                    if wsdot_validation:
                        rid = standardize_route_id(
                            rid, RouteIdSuffixType.has_no_suffix)
                except ValueError as error:
                    row[3] = "%s" % error
                else:
                    # If direction is None, skip regex and set match result to None.
                    if direction:
                        match = decrease_re.match(direction)
                    else:
                        match = None

                    # If direction is "d" and specified suffix type has "d" suffixes, add "d" suffix.
                    if match and route_id_suffix_type & RouteIdSuffixType.has_d_suffix == RouteIdSuffixType.has_d_suffix:
                        rid = "%s%s" % (rid, "d")
                    # Add the "i" suffix for non-"d" if specified suffix type includes "i" suffixes.
                    elif route_id_suffix_type & RouteIdSuffixType.has_i_suffix:
                        rid = "%s%s" % (rid, "i")
                    row[2] = rid
            else:
                # If no route ID value, add error message to error field.
                row[3] = "Input Route ID is null"
            cursor.updateRow(row)


def create_event_feature_class(event_table,
                               route_layer,
                               event_table_route_id_field,
                               route_layer_route_id_field,
                               begin_measure_field,
                               end_measure_field=None,
                               out_fc=None):
    """Creates a feature class by locating events along a route layer.

    Args:
        event_table: str, path to a table containing route events
        route_layer: str, path to layer or feature class containing route polylines
        event_table_route_id_field: name of the field in event_table that specifies route ID.
        route_layer_route_id_field: name of the field in the route_layer that specifies route ID.
        begin_measure_field: name of numeric field in event_table that contains begin measure value
        end_measure_field: Optional. Name of numeric field in event_table that contains end measure
            value. If omitted, begin_measure_field will be interpereted as a point along a line
            instead of a line segment.
        out_fc: str, path to output feature class. If omitted, an in_memory FC will be created

    Returns:
        Returns the path to the output feature class.
    """

    # # Ensure given event table and route layer exist.
    # if not arcpy.Exists(event_table):
    #     raise FileNotFoundError(event_table)
    # elif not arcpy.Exists(route_layer):
    #     raise FileNotFoundError(route_layer)

    # End measure is optional. If omitted, out geometry will be points.
    # Otherwise, output will be polyline.
    if end_measure_field is not None:
        fields = ("OID@", event_table_route_id_field,
                  begin_measure_field, end_measure_field)
        out_geo_type = "POLYLINE"
    else:
        fields = ("OID@", event_table_route_id_field, begin_measure_field)
        out_geo_type = "POINT"

    if out_fc is None:
        wkspc = "in_memory"
        out_fc = arcpy.CreateUniqueName("LocatedEvents", wkspc)

    # Create the output feature class.
    workspace, fc_name = split_path(out_fc)
    routes_desc = Describe(route_layer)

    # Get the spatial reference from the route layer description.
    # The method for accessing it will differ in ArcGIS Desktop
    # and ArcGIS Pro.
    spatial_reference = None
    if isinstance(routes_desc, dict):
        spatial_reference = routes_desc["spatialReference"]
    else:
        spatial_reference = routes_desc.spatialReference

    arcpy.management.CreateFeatureclass(workspace, fc_name, out_geo_type,
                                        spatial_reference=spatial_reference)
    event_oid_field_name = "EventOid"
    error_field_name = "Error"
    arcpy.management.AddField(out_fc, event_oid_field_name, "LONG", field_alias="Event OID",
                              field_is_nullable=False, field_is_required=True)
    arcpy.management.AddField(out_fc, error_field_name, "TEXT", field_is_nullable=True,
                              field_alias="Locating Error")

    with arcpy.da.SearchCursor(event_table, fields) as table_cursor:
        with arcpy.da.InsertCursor(out_fc, (event_oid_field_name, "SHAPE@",
                                            error_field_name)) as insert_cursor:
            for row in table_cursor:
                event_oid = row[0]
                event_route_id = row[1]
                begin_m = row[2]
                if len(fields) >= 4:
                    end_m = row[3]
                else:
                    end_m = None

                where = "%s = '%s'" % (
                    route_layer_route_id_field, event_route_id)
                out_geom = None
                error = None
                with arcpy.da.SearchCursor(route_layer, "SHAPE@", where) as route_cursor:
                    # Initialize output route event geometry.
                    for (geom,) in route_cursor:
                        # find position or segment.
                        try:
                            if end_m is None:
                                out_geom = geom.positionAlongLine(begin_m)
                            else:
                                out_geom = geom.segmentAlongLine(
                                    begin_m, end_m)
                        except arcpy.ExecuteError as ex:
                            error = ex
                            arcpy.AddWarning("Error finding event on route: %s @ %s.\n%s" % (
                                event_route_id, (begin_m, end_m), ex))
                        # If out geometry has been found, no need to try with other
                        # route features. (There should be only one route feature,
                        # anyway.)
                        if out_geom:
                            error = None
                            break
                if error:
                    insert_cursor.insertRow((event_oid, None, str(error)))
                elif out_geom is None:
                    msg = "Could not locate %s on %s (%s)." % (
                        (begin_m, end_m), event_route_id, event_route_id)
                    insert_cursor.insertRow((event_oid, None, msg))
                    arcpy.AddWarning(msg)
                else:
                    insert_cursor.insertRow((event_oid, out_geom, None))

    return out_fc


def field_list_contains(fields, name, field_type="TEXT"):
    """Determines if a list of fields contains a field with the given name and type.

    Args:
        fields: A Python list of fields. This can be acquired from arcpy.ListFields or arcpy(.da).Describe.
        name: The name of the field to search for. Match is case-insensitive.
        type_re: An re that matches the given field type. Defaults to match either "String" or "Text"
                 (case-insensitive).

    Returns:
        Returns a tuple with two boolean values. The first tells if the field with the given name is
        contained in the list; the second tells if the type of the field matches the desired type.
        (This second value will always be False if the field is not found.)

    Example:
        fields = arcpy.ListFields(r"c:/temp/example.gdb/my_features")
        field_exists, correct_type = _field_list_contains(fields, "LOC_ERROR")
    """

    field_mapping = {
        "BLOB": "Blob",
        "DATE": "Date",
        "DOUBLE": "Double",
        # "Geometry": "Geometry",
        # "GlobalID": "GlobalID",
        "GUID": "Guid",
        "LONG": "Integer",
        # "OID": "OID",
        # "Raster": "Raster",
        "FLOAT": "Single",
        "SHORT": "SmallInteger",
        "TEXT": "String"
    }

    type_re_parts = "|".join(
        map(lambda s: r"(?:%s)" % s, (field_type, field_mapping[field_type]))
    )

    type_re = re.compile(r"^(?:%s)$" % type_re_parts, re.IGNORECASE)

    field_exists = False
    correct_type = False
    name_re = re.compile("^%s$" % name)
    for field in fields:
        if name_re.match(field.baseName) or name_re.match(field.name):
            field_exists = True
            if type_re.match(field.type):
                correct_type = True
            break
    return field_exists, correct_type


def get_measures(in_geometry, route_geometry):
    """Finds the nearest point or route segement along a route polyline.

    Args:
        in_geometry: Either a PointGeometry or a Polyline.
        route_geometry: A route Polyline.

    Returns:
        A tuple with the following values
            * located geometry
            * Begin, End point info tuples: (nearest_point, measure, distance, right_site)
                Will contain one item if input is point, two if input is polyline.

    """
    if not isinstance(route_geometry, arcpy.Polyline):
        raise TypeError("route_geometry must be a Polyline.")
    p1_info, p2_info = (None,) * 2
    if isinstance(in_geometry, (arcpy.PointGeometry, arcpy.Polyline)):
        p1_info = route_geometry.queryPointAndDistance(in_geometry.firstPoint)
        if isinstance(in_geometry, arcpy.Polyline):
            p2_info = route_geometry.queryPointAndDistance(
                in_geometry.lastPoint)
            out_geometry = route_geometry.segmentAlongLine(
                p1_info[1], p2_info[1])
        else:
            out_geometry = p1_info[0]
    else:
        raise TypeError("Invalid geometry type")
    return out_geometry, p1_info, p2_info


def update_route_location(
        in_features,
        route_layer,
        in_features_route_id_field,
        route_layer_route_id_field,
        measure_field,
        end_measure_field=None,
        rounding_digits=None,
        use_m_from_route_point=True):
    """Given input features, finds location nearest route.

    Args:
        in_features: Input features to be located. (Feature Layer)
        route_layer: Route layer containing Linear Referencing System (LRS)
        in_features_route_id_field: The field in "in_features" that identifies which route the event is on.
        route_layer_route_id_field: The field in the "route_layer" that contains the unique route identifier.
        measure_field: The field in the input features with begin measures (for lines) or a point's measure (for points).
        end_measure_field: The field in the input features with end measures (for lines). Not used if in_features are points.
        rounding_digits: The number of digits to round to.
        use_m_from_route_point: If you want to use the M value from the nearest point (rather than the distance returned by
        queryPointAndDistance) set to True. Otherwise, set to False
    """

    # Convert rounding digits to integer
    if not isinstance(rounding_digits, (int, type(None))):
        rounding_digits = int(rounding_digits)

    # out_rid_field: Name of the route ID field in the output feature class.
    # out_error_field: The name of the new field for error information that will be created in "out_fc".
    # source_oid_field: The name of the source Object ID field in the output feature class.

    out_error_field = "LOC_ERROR"
    distance_1_field = "Distance"
    distance_2_field = "EndDistance"

    route_desc = Describe(route_layer)
    in_features_desc = Describe(in_features)

    if not re.match(r"^(?:(?:Point)|(?:Polyline))$", in_features_desc.shapeType, re.IGNORECASE):
        raise TypeError(
            "Input feature class must be either Point or Polyline.")

    spatial_ref = route_desc.spatialReference

    def add_output_fields(field_name, field_type, **other_add_field_params):
        field_exists, correct_type = field_list_contains(
            in_features_desc.fields, field_name, field_type)

        if not field_exists:
            arcpy.management.AddField(
                in_features, field_name, field_type, **other_add_field_params)
        elif not correct_type:
            arcpy.AddError(
                "Field '%s' already exists in table but is not the correct type." % field_name)
        else:
            arcpy.AddWarning(
                "Field '%s' already exists and its data will be overwritten." % field_name)

    # Locating Error field
    add_output_fields(out_error_field, "TEXT", field_alias="Locating Error")
    add_output_fields(distance_1_field, "DOUBLE", field_alias="Distance")

    update_fields = [in_features_route_id_field,
                     "SHAPE@", out_error_field, measure_field, distance_1_field]
    if end_measure_field:
        add_output_fields(distance_2_field, "DOUBLE",
                          field_alias="End Distance")
        update_fields += [end_measure_field, distance_2_field]

    # Get search cursor feature count
    result = arcpy.management.GetCount(in_features)
    feature_count = int(result.getOutput(0))

    error_count = 0

    with arcpy.da.UpdateCursor(in_features, update_fields, "%s IS NOT NULL" % in_features_route_id_field, spatial_ref) as update_cursor:
        for row in update_cursor:
            in_route_id, event_geometry = row[:2]

            if not event_geometry:
                row[2] = "Event geometry is NULL."
                continue

            with arcpy.da.SearchCursor(route_layer, ["SHAPE@"], "%s = '%s'" % (route_layer_route_id_field, in_route_id)) as route_cursor:
                route_geometry = None
                for route_row in route_cursor:
                    route_geometry = route_row[0]
                    updated_geometry, begin_info, end_info = get_measures(
                        event_geometry, route_geometry)

                    # the updated_geometry is not needed for this.
                    del updated_geometry

                    # Geometry should not change, so no need to update it.
                    # row[1] = updated_geometry
                    nearest_point, measure, distance, right_side = begin_info
                    if use_m_from_route_point:
                        measure = nearest_point.firstPoint.M
                    if rounding_digits is not None:
                        measure = round(measure, rounding_digits)
                    del right_side
                    row[2] = None
                    row[3], row[4] = measure, distance
                    # row[3] = m1
                    # row[5], row[4] = angle_dist1
                    if end_measure_field:
                        nearest_point, measure, distance, right_side = end_info
                        del right_side

                        if use_m_from_route_point:
                            measure = nearest_point.firstPoint.M

                        if rounding_digits is not None:
                            measure = round(measure, rounding_digits)
                        row[-2] = measure
                        row[-1] = distance
                    break
                if not route_geometry:
                    row[2] = "Route not found"
                    error_count += 1
            update_cursor.updateRow(row)

    if error_count:
        arcpy.AddWarning("Unable to locate %d out of %d events." %
                         (error_count, feature_count))


def copy_with_segment_ids(input_point_features, out_feature_class):
    """Copies point feature classes and adds SegmentID and IsEndPoint fields to the copy.

    Parameters:
        input_point_features: Path to a point feature class.
        out_feature_class: Path where output feature class will be written. This feature class
        will contain the following extra fields:
            SegmentId:  Indicates which point features of input_point_features go together to define the
                        begin and end points of a line segement.
            IsEndPoint: Will have value of 1 if the the row represents an end point, 0 for a
                        begin point.
    Returns:
        Returns a tuple: total number of rows (r), number of segments (s).
        s = r / 2
    """
    row_count = int(arcpy.GetCount_management(input_point_features)[0])
    if row_count % 2 != 0:
        raise ValueError(
            "Input feature class should have an even number of features.")

    arcpy.AddMessage("Copying %s to %s..." %
                     (input_point_features, out_feature_class))
    arcpy.management.CopyFeatures(input_point_features, out_feature_class)
    arcpy.AddMessage("Adding fields %s to %s" %
                     (("SegmentId", "IsEndPoint"), out_feature_class))
    arcpy.management.AddField(
        out_feature_class, "SegmentId", "LONG", field_alias="Segement ID")
    arcpy.management.AddField(
        out_feature_class, "IsEndPoint", "SHORT", field_alias="Is end point")

    arcpy.AddMessage(
        "Calculating SegmentIDs and determining start and end points.")
    i = -1
    segment_id = -1
    with arcpy.da.UpdateCursor(out_feature_class, ("SegmentId", "IsEndPoint")) as cursor:
        # Need to iterate through row, but not actually use the variable itself
        for row in cursor:
            # row is not actually used
            del row
            i += 1
            is_end_point = False
            if i % 2 == 0:
                segment_id += 1
            else:
                is_end_point = True
            cursor.updateRow([segment_id, int(is_end_point)])

    return i + 1, segment_id + 1


def _list_oids_of_non_matches(table, match_field1, match_field2):
    """Returns a list of the OIDs of rows where the values in match_field1
    and match_field2 do not match.
    """
    # Get a list of OIDs that need to be deleted.
    # These are the rows where the begin and end route IDs do not match.
    oids_to_be_deleted = []
    with arcpy.da.SearchCursor(table, ["OID@", match_field1, match_field2]) as cursor:
        for row in cursor:
            oid, field1, field2 = row
            if field1 != field2:
                oids_to_be_deleted.append(oid)
    return oids_to_be_deleted


def _select_by_oids(table, oid_list):
    """Creates a new table view and selects all rows with object IDs
    that are in the input OID list.
    """
    # Return nothing if the OID list is empty or None.
    if not oid_list:
        return

    # Create the name for the table view.
    events_layer = split_path(arcpy.CreateScratchName(
        "OutputEvents", workspace="in_memory"))[1]
    arcpy.AddMessage(
        "Rows with the following OIDs should be deleted: %s" % oid_list)
    arcpy.AddMessage("Creating view %s on %s" % (events_layer, table))
    arcpy.management.MakeTableView(table, events_layer)

    # Get OID field name
    oid_field = arcpy.ListFields(table, field_type="OID")[0]
    oid_list = ",".join(map(str, oid_list))
    arcpy.management.SelectLayerByAttribute(
        events_layer, "NEW_SELECTION", "%s in (%s)" % (oid_field.name, oid_list))

    return events_layer


def points_to_line_events(in_features, in_routes, route_id_field, radius, out_table):
    """Using a point feature layer to represent begin and end points, finds nearest
    route event points.
    For parameter explanations, see http://pro.arcgis.com/en/pro-app/tool-reference/linear-referencing/locate-features-along-routes.htm

    Returns
        Returns a tuple: (out_table, output event features for use with arcpy.lr.MakeRouteEventLayer)
    """
    # Copy input features to new temporary feature class.
    in_features_copy = arcpy.CreateScratchName(workspace="in_memory")

    # Determine the segment IDs and store in Numpy structured array.
    copy_with_segment_ids(in_features, in_features_copy)

    temp_events_table = arcpy.CreateScratchName(
        "AllEvents", workspace="in_memory")

    try:
        arcpy.AddMessage("Locating fields along routes...")
        arcpy.lr.LocateFeaturesAlongRoutes(
            in_features_copy, in_routes, route_id_field, radius, temp_events_table,
            "RID POINT Measure", "ALL", "DISTANCE", in_fields="FIELDS")
    finally:
        arcpy.AddMessage("Deleting %s" % in_features_copy)
        arcpy.management.Delete(in_features_copy)

    # Create layer name, removing the workspace part from the generated output.
    events_layer = split_path(
        arcpy.CreateUniqueName("point_events", "in_memory"))[1]
    end_events_table = arcpy.CreateScratchName(
        "End", "PointEvents", workspace="in_memory")

    try:
        # Select start point events, copy to new table.
        # Then switch the selection and copy the end point events to a new table.
        arcpy.management.MakeTableView(
            temp_events_table, events_layer, None, "in_memory")

        arcpy.management.SelectLayerByAttribute(
            events_layer, "NEW_SELECTION", "IsEndPoint = 0")

        # copy selection to output table
        arcpy.management.CopyRows(events_layer, out_table)

        arcpy.management.SelectLayerByAttribute(
            events_layer, "SWITCH_SELECTION")

        # copy selection to new temp table
        arcpy.management.CopyRows(events_layer, end_events_table)

        # Alter the field names in the end point events table
        for field_name in ("RID", "Measure", "Distance"):
            new_name = "End%s" % field_name
            arcpy.management.AlterField(end_events_table, field_name, new_name)

        # Join the temp table end point data to the output table containg the begin point events.
        arcpy.management.JoinField(
            out_table, "SegmentId", end_events_table, "SegmentId", [
                "EndRID", "EndMeasure", "EndDistance"])

    finally:
        for table in (events_layer, temp_events_table, end_events_table):
            if table and arcpy.Exists(table):
                arcpy.AddMessage("Deleting %s..." % table)
                arcpy.management.Delete(table)

    # Get a list of OIDs that need to be deleted.
    # These are the rows where the begin and end route IDs do not match.
    oids_to_be_deleted = _list_oids_of_non_matches(
        out_table, "RID", "EndRID")

    drop_end_rid_field = True

    # Delete rows from the output table where the start and end route IDs do not match
    if oids_to_be_deleted:
        try:
            # # This didn't work for some reason, so now select rows for deletion using alternative method.
            # # arcpy.management.SelectLayerByAttribute(events_layer, "NEW_SELECTION", "RID <> EndRID")

            events_layer = _select_by_oids(out_table, oids_to_be_deleted)

            selected_row_count = _get_row_count(events_layer)
            drop_end_rid_field = True
            if selected_row_count:
                total_rows_before_delete = _get_row_count(out_table)
                arcpy.AddMessage(
                    "There are %d rows where the start and end RIDs do not match. Deleting these rows..." % selected_row_count)
                arcpy.management.DeleteRows(events_layer)
                rows_after_delete = _get_row_count(out_table)
                if rows_after_delete >= total_rows_before_delete:
                    arcpy.AddWarning(
                        "%d rows were selected for deletion, but no rows were deleted." % selected_row_count)
                    drop_end_rid_field = False
            else:
                arcpy.AddMessage("Zero rows were selected for deletion")
        finally:
            arcpy.management.Delete(events_layer)

    if drop_end_rid_field:
        for field in ("EndRID", "SegmentID", "IsEndPoint"):
            try:
                arcpy.DeleteField_management(out_table, field)
            except arcpy.ExecuteError as ex:
                arcpy.AddWarning(
                    "Could not delete field %s from %s.\n%s" % (field, out_table, ex))

    return out_table, "RID LINE Measure EndMeasure"


def points_to_line_event_features(in_features, in_routes, route_id_field, radius, out_feature_class):
    """Given an input feature layer of points representing route segment start and end points,
    locates those points along the given route layer's routes and returns the output route line segment
    event feature class.
    """
    # Create name for temporary event table.
    event_table = arcpy.CreateScratchName(
        "event_table", workspace="in_memory")
    # Create line events for input point features, writing to the event_table.
    event_table, event_properties = points_to_line_events(in_features, in_routes,
                                                          route_id_field, radius, event_table)
    # Create a name for the event layer.
    event_layer = split_path(arcpy.CreateScratchName(
        "located_events", workspace="in_memory"))[1]
    # Create the event layer.
    arcpy.lr.MakeRouteEventLayer(
        in_routes, route_id_field, event_table, event_properties, event_layer, None, "ERROR_FIELD")
    # Copy the event layer to a feature class.
    arcpy.management.CopyFeatures(event_layer, out_feature_class)
    # Delete the temporary tables and layers.
    for item in (event_layer, event_table):
        if item and arcpy.Exists(item):
            arcpy.management.Delete(item)
