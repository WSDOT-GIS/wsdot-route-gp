"""Allows user to locate points or route segments along WA routes.
"""
from __future__ import (unicode_literals, print_function, division,
                        absolute_import)

import re
from os.path import split as split_path, join as join_path
import arcpy


class RouteIdSuffixType(object):
    """Specifies valid route ID suffix types.
    Values can be combined as bitflags (e.g, 1 | 2).
    """
    has_no_suffix = 0
    has_i_suffix = 1
    has_d_suffix = 2
    has_both_i_and_d = 1 | 2


def standardize_route_id(route_id, route_id_suffix_type=RouteIdSuffixType.has_both_i_and_d):
    """Converts a route ID string from an event table into
    the format used in the route layer.

    Args:
        route_id: Route ID string from event table.
        route_id_suffix_type: Optional. Indicates what format the route_layer's route IDs are in.
            See the RouteIdSuffixType values. Defaults to RouteIdSUffixType.has_both_i_and_d.

    Returns:
        str: equivalent of the input route id in the output format.

    Raises:
        ValueError: Incorrectly formatted route_id.
    """
    # RE matches a WSDOT route ID with optional direction suffix.
    # Captures route_id, sr, rrt, rrq, and dir groups.
    route_re = re.compile(
        r"""^(?P<route_id>
                    # 3-digit mainline route identifier
                    (?P<sr>\d{3})
                    (?: # rrt and rrq may or may not be present
                        (?P<rrt>
                            (AR)|
                            (CO)|
                            (F[ST])|
                            (PR)|
                            (RL)|
                            (SP)|
                            (TB)|
                            (TR)|
                            (LX)|
                            ([CFH][DI])|
                            ([PQRS][1-9])|
                            (UC)
                        )
                        # rrt can exist without rrq.
                        (?P<rrq>[A-Z0-9]{0,6})
                    )?
                )(?P<dir>[id]?)$""", re.VERBOSE)
    # This RE matches formats such as I-5, US-101, WA-8, or SR-8.
    # The numerical value will be captured.
    route_label_format_re = re.compile(r"^[A-Z]+[\-\s](\d{0,3})$")

    match = route_re.match(route_id)
    if match:
        unsuffixed_rid = match.group("route_id")
        direction = match.group("dir")
        if route_id_suffix_type == RouteIdSuffixType.has_no_suffix:
            return unsuffixed_rid
        if direction:
            return "%s%s" % (unsuffixed_rid, direction)
        return "%si" % unsuffixed_rid
    else:
        match = route_label_format_re.match(route_id)
        if not match:
            raise ValueError("Incorrectly formatted route_id: %s." % route_id)
        # Pad route number to three digits.
        unsuffixed_rid = match.group(1).rjust(3, "0")
        if route_id_suffix_type & RouteIdSuffixType.has_i_suffix == RouteIdSuffixType.has_i_suffix:
            return "%si" % unsuffixed_rid
        return unsuffixed_rid


def add_standardized_route_id_field(in_table, route_id_field, direction_field, out_field_name, out_error_field_name, route_id_suffix_type):
    """Adds route ID + direction field to event table that has both unsuffixed route ID and direction fields.
    """
    # Make sure an output route ID suffix type other than "unsuffixed" has been specified.
    if route_id_suffix_type == RouteIdSuffixType.has_no_suffix:
        raise ValueError("Invalid route ID suffix type: %s" %
                         route_id_suffix_type)

    # Determine the length of the output route ID field based on route suffix type
    out_field_length = 11
    if route_id_suffix_type == RouteIdSuffixType.has_i_suffix or route_id_suffix_type == RouteIdSuffixType.has_d_suffix:
        out_field_length += 1
    elif route_id_suffix_type == RouteIdSuffixType.has_both_i_and_d:
        out_field_length += 2

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
                               route_id_suffix_type=RouteIdSuffixType.has_i_suffix |
                               RouteIdSuffixType.has_d_suffix,
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
        route_id_suffix_type: Optional. Indicates what format the route_layer's route IDs are in.
            See the RouteIdSuffixType values.
        out_fc: str, path to output feature class. If omitted, and in_memory FC will be created

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
    routes_desc = arcpy.Describe(route_layer)
    # arcpy.management.CreateFeatureclass(workspace, fc_name, out_geo_type, None, "ENABLED",
    #                                     "DISABLED", routes_desc.spatialReference)
    arcpy.management.CreateFeatureclass(workspace, fc_name, out_geo_type,
                                        spatial_reference=routes_desc.spatialReference)
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

                try:
                    std_route_id = standardize_route_id(
                        event_route_id, route_id_suffix_type)
                except ValueError as ex:
                    msg = "Invalid route ID at OID %d: %s" % (
                        event_oid, event_route_id)
                    insert_cursor.insertRow((event_oid, None, msg))
                    continue

                where = "%s = '%s'" % (
                    route_layer_route_id_field, std_route_id)
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
                                std_route_id, (begin_m, end_m), ex))
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
                        (begin_m, end_m), std_route_id, event_route_id)
                    insert_cursor.insertRow((event_oid, None, msg))
                    arcpy.AddWarning(msg)
                else:
                    insert_cursor.insertRow((event_oid, out_geom, None))

    return out_fc

def update_route_location(
        in_features,
        route_layer,
        in_features_route_id_field,
        route_layer_route_id_field,
        out_fc):
    """Given input features, finds location nearest route.

    Args:
        in_features: Input features to be located. (Feature Layer)
        route_layer: Route layer containing Linear Referencing System (LRS)
        in_features_route_id_field: The field in "in_features" that identifies which route the event is on.
        route_layer_route_id_field: The field in the "route_layer" that contains the unique route identifier.
        out_fc: Path to the output feature class that this function will create.
    """

    # Split output path into workspace and feature class name.
    out_workspace, out_fc_name = split_path(out_fc)

    # out_rid_field: Name of the route ID field in the output feature class.
    # out_error_field: The name of the new field for error information that will be created in "out_fc".
    # source_oid_field: The name of the source Object ID field in the output feature class.

    out_rid_field = "RID"
    out_error_field = "LOC_ERROR"
    source_oid_field = "SOURCE_OID"
    m1_field = "M"
    m2_field = "M2"

    if not out_workspace:
        raise ValueError(
            "No workspace specified in output feature class path: '%s'" % out_fc)
    elif not arcpy.Exists(out_workspace):
        arcpy.AddError("Workspace does not exist: '%s'." %
                       out_fc)  # this also raises exception
    elif not arcpy.env.overwriteOutput and arcpy.Exists(out_fc):
        arcpy.AddError("Feature class already exists: '%s'" % out_fc)

    if "Describe" in dir(arcpy.da):
        route_desc = arcpy.da.Describe(route_layer)
        in_features_desc = arcpy.da.Describe(in_features)
    else:
        route_desc = arcpy.Describe(route_layer)
        in_features_desc = arcpy.Describe(in_features)

    if not re.match(r"^(?:(?:Point)|(?:Polyline))$", in_features_desc.shapeType, re.IGNORECASE):
        raise TypeError(
            "Input feature class must be either Point or Polyline.")

    spatial_ref = route_desc.spatialReference

    # Create the output feature class
    arcpy.management.CreateFeatureclass(
        out_workspace, out_fc_name, in_features_desc.shapeType.upper(), has_m="ENABLED", spatial_reference=spatial_ref)
    # Use AddFields if available. (ArcGIS Pro 2.0: Yes, ArcGIS Desktop 10.5.1: No)
    # Otherwise, default to multiple calls to AddField.

    field_defs = (
        [source_oid_field, "LONG", "Source OID", None, None],
        [out_rid_field, "STRING", "Route ID", 12, None],
        [out_error_field, "STRING", "Locating Error", None, None],
        [m1_field, "DOUBLE", "Measure", None, None],
        [m2_field, "DOUBLE", "End Measure", None, None])

    if "AddFields_management" in dir(arcpy):
        arcpy.management.AddFields(out_fc, field_defs)
    else:
        for field_def in field_defs:
            arcpy.management.AddField(
                out_fc, field_def[0], field_def[1], field_alias=field_def[2], field_length=field_def[3])

    insert_fields = [source_oid_field,
                     out_rid_field, "SHAPE@", out_error_field, m1_field, m2_field]
    search_fields = ["OID@", in_features_route_id_field, "SHAPE@"]

    pointRe = re.compile(r"^point$", re.IGNORECASE)
    polylineRe = re.compile(r"^polyline$", re.IGNORECASE)

    with arcpy.da.InsertCursor(out_fc, insert_fields) as insert_cursor:
        # Get search cursor feature count
        result = arcpy.management.GetCount(in_features)
        feature_count = int(result.getOutput(0))
        arcpy.AddMessage("There are %s features" % feature_count)
        # Loop through the input features that have non-null route ID values.
        i = int(0)
        with arcpy.da.SearchCursor(in_features, search_fields, "%s IS NOT NULL" % in_features_route_id_field) as search_cursor:
            arcpy.SetProgressor(
                "step", "Searching features...", 0, feature_count)
            for row in search_cursor:
                arcpy.SetProgressorLabel("%d of %d" % (i, feature_count))
                i += 1
                if arcpy.env.isCancelled:
                    break
                try:
                    in_geometry = row[2]
                    if not in_geometry:
                        continue
                    route_where_clause = "%s = '%s'" % (
                        route_layer_route_id_field, row[1])
                    with arcpy.da.SearchCursor(route_layer, ["SHAPE@"], route_where_clause) as route_cursor:
                        # Locate points along route
                        new_row = None
                        for route_row in route_cursor:
                            if arcpy.env.isCancelled:
                                break
                            route_line = route_row[0]
                            # Initialize route event geometry to None.
                            out_geometry = None
                            try:
                                if polylineRe.match(in_geometry.type):
                                    # Snap the first and last points in input line segment to route.
                                    p1 = route_line.snapToLine(
                                        in_geometry.firstPoint)
                                    p2 = route_line.snapToLine(
                                        in_geometry.lastPoint)
                                    # Get the measures of the snapped points.
                                    m1 = route_line.measureOnLine(p1)
                                    m2 = route_line.measureOnLine(p2)
                                    # Get a line segment using the measures.
                                    out_geometry = route_line.segmentAlongLine(
                                        m1, m2)
                                elif pointRe.match(in_geometry.type):
                                    out_geometry = route_line.snapToLine(
                                        in_geometry)
                                    m1 = route_line.measureOnLine(out_geometry)
                                else:
                                    raise TypeError(
                                        "Unexpected geometry type: %s" % in_geometry.type)
                            except arcpy.ExecuteError as ex:
                                new_row = row[:2] + \
                                    (None, "%s" % ex, None, None)
                            else:
                                if out_geometry:
                                    # Initialize null measures
                                    m1, m2 = (None,) * 2

                                    # For lines, set m1 and m2 to line start and end points' measures.
                                    # For points, set m1 to output_geometry point's measure and leave m2 as None.
                                    if polylineRe.match(out_geometry.type):
                                        m1, m2 = map(lambda point: point.M, (out_geometry.firstPoint, out_geometry.lastPoint))
                                    elif pointRe.match(out_geometry.type):
                                        m1 = out_geometry.firstPoint.M

                                    new_row = row[:2] + (out_geometry, None, m1, m2)
                            break  # There should only be one row
                        if not new_row:
                            # If new_row is None, then there was no match in the input route layer.
                            # Add a new row with this error message.
                            new_row = row[:2] + (None, "Route not found", None, None)
                        try:
                            insert_cursor.insertRow(new_row)
                        except RuntimeError as rte:
                            arcpy.AddWarning(
                                "Error inserting row %s\n%s" % (new_row, rte))
                finally:
                    arcpy.SetProgressorPosition()
            arcpy.ResetProgressor()
