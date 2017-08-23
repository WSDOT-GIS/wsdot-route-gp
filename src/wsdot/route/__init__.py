"""Allows user to locate points or route segments along WA routes.
"""
from __future__ import (unicode_literals, print_function, division,
                        absolute_import)

import re
import arcpy
from os.path import split as split_path


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
                        (?P<rrt>[A-Z0-9]{2})
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
        else:
            if direction:
                return "%s%s" % (unsuffixed_rid, direction)
            else:
                return "%si" % unsuffixed_rid
    else:
        match = route_label_format_re.match(route_id)
        if not match:
            raise ValueError("Incorrectly formatted route_id: %s." % route_id)
        # Pad route number to three digits.
        unsuffixed_rid = match.group(1).rjust(3, "0")
        if route_id_suffix_type & RouteIdSuffixType.has_i_suffix == RouteIdSuffixType.has_i_suffix:
            return "%si" % unsuffixed_rid
        else:
            return unsuffixed_rid


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
                    msg = "Invalid route ID at OID %d: %s" % (event_oid, event_route_id)
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
