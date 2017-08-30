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
            # Get unsuffixed, standardized route ID.
            try:
                rid = standardize_route_id(
                    rid, RouteIdSuffixType.has_no_suffix)
            except ValueError as error:
                row[3] = "%s" % error
            else:
                match = decrease_re.match(direction)
                if match and route_id_suffix_type & RouteIdSuffixType.has_d_suffix == RouteIdSuffixType.has_d_suffix:
                    rid = "%s%s" % (rid, "d")
                elif route_id_suffix_type & RouteIdSuffixType.has_i_suffix:
                    rid = "%s%s" % (rid, "i")
                row[2] = rid
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
                        except Exception as ex:
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


def find_route_location(
        in_features,
        route_layer,
        in_features_route_id_field,
        route_layer_route_id_field,
        out_fc,
        out_rid_field="RID",
        out_error_field="LOC_ERROR",
        source_oid_field="SOURCE_OID",
        route_id_suffix_type=RouteIdSuffixType.has_both_i_and_d):
    """Given input features, finds location nearest route.

    Args:
        in_features: Input features to be located. (Feature Layer)
        route_layer: Route layer containing Linear Referencing System (LRS)
        in_features_route_id_field: The field in "in_features" that identifies which route the event is on.
        route_layer_route_id_field: The field in the "route_layer" that contains the unique route identifier.
        out_fc: Path to the output feature class that this function will create.
        out_rid_field: Name of the route ID field in the output feature class.
        out_error_field: The name of the new field for error information that will be created in "out_fc".
        source_oid_field: The name of the source Object ID field in the output feature class.
        route_id_suffix_type: Specifies the format of the route id and how direction information is appended (if at all).
    """

    # Split output path into workspace and feature class name.
    out_workspace, out_fc_name = split_path(out_fc)

    if not out_workspace:
        raise ValueError(
            "No workspace specified in output feature class path: '%s'" % out_fc)
    elif not arcpy.Exists(out_workspace):
        arcpy.AddError("Workspace does not exist: '%s'." %
                       out_fc)  # this also raises exception
    elif not arcpy.env.overwriteOutput and arcpy.Exists(out_fc):
        arcpy.AddError("Feature class already exists: '%s'" % out_fc)

    route_desc = arcpy.da.Describe(route_layer)
    spatial_ref = route_desc.spatialReference

    # Create the output feature class
    arcpy.management.CreateFeatureclass(
        out_workspace, out_fc_name, "Polyline", None, True, False, spatial_reference=spatial_ref)
    # Use AddFields if available. (ArcGIS Pro 2.0: Yes, ArcGIS Desktop 10.5.1: No)
    # Otherwise, default to multiple calls to AddField.
    if "AddFields_management" in dir(arcpy):
        arcpy.management.AddFields(out_fc, (
            [source_oid_field, "LONG", "Source OID", None, None],
            [out_rid_field, "STRING", "Route ID", 12, None],
            [out_error_field, "STRING", "Locating Error", None, None]
        ))
    else:
        arcpy.management.AddField(out_fc, source_oid_field,
                                  "LONG", field_alias="Source OID")
        arcpy.management.AddField(
            out_fc, out_rid_field, "STRING", field_length=12, field_alias="Route ID")
        arcpy.management.AddField(out_fc, out_error_field, field_alias="Locating Error")

    with arcpy.da.InsertCursor(out_fc, [source_oid_field, out_rid_field, out_error_field, "SHAPE@"]) as insert_cursor:
        # Loop through the input features that have non-null route ID values.
        with arcpy.da.SearchCursor(in_features, [
            "@OID",
            in_features_route_id_field,
            "SHAPE@"
        ], "%s IS NOT NULL" % in_features_route_id_field) as search_cursor:
            for row in search_cursor:
                in_line = row[2]
                route_where_clause = "%s = '%s'" % (
                    route_layer_route_id_field, row[1])
                with arcpy.da.SearchCursor(route_layer, ["SHAPE@"], route_where_clause) as route_cursor:
                    # Locate points along route
                    new_row = None
                    for route_row in route_cursor:
                        route_line = route_row[0]
                        try:
                            # Snap the first and last points in input line segment to route.
                            p1 = route_line.snapToLine(in_line.firstPoint)
                            p2 = route_line.snapToLine(in_line.lastPoint)
                            # Get the measures of the snapped points.
                            m1 = route_line.measureOnLine(p1)
                            m2 = route_line.measureOnLine(p2)
                            # Get a line segment using the measures.
                            segment = route_line.segmentAlongLine(m1, m2)
                        except Exception as ex:
                            new_row = row[:3] + ("%s" % ex,)
                        else:
                            new_row = row[:3] + (None, segment)
                        break  # There should only be one row
                    if new_row:
                        insert_cursor.insertRow(new_row)
                    else:
                        # If new_row is None, then there was no match in the input route layer.
                        # Add a new row with this error message.
                        new_row = row[:3] + ("Route not found",)
                        insert_cursor.insertRow(new_row)
