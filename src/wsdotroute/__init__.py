"""Allows user to locate points or route segments along WA routes.
"""
from __future__ import (unicode_literals, print_function, division,
                        absolute_import)

import re
from os.path import split as split_path, join as join_path
import arcpy
try:
    from arcpy.da import Describe
except ImportError:
    from arcpy import Describe


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


def field_list_contains(fields, name, type_re=re.compile(r"^(?:(?:String)|(?:Text))$", re.IGNORECASE)):
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
            * begin measure (or only measure for points)
            * end measure (or None for points)
    """
    if not isinstance(route_geometry, arcpy.Polyline):
        raise TypeError("route_geometry must be a Polyline.")

    m1, m2, out_geometry = (None,) * 3
    if isinstance(in_geometry, arcpy.PointGeometry):
        # nearest_point, distance_from_start, min_distance, right_side =  route_geometry.queryPointAndDistance(in_geometry.firstPoint)
        out_geometry = route_geometry.snapToLine(in_geometry.firstPoint)
        m1 = out_geometry.firstPoint.M
    elif isinstance(in_geometry, arcpy.Polyline):
        p1, p2 = map(route_geometry.snapToLine, (in_geometry.firstPoint, in_geometry.lastPoint))
        m1 = p1.firstPoint.M
        m2 = p2.firstPoint.M
        out_geometry = route_geometry.segmentAlongLine(m1, m2)
    else:
        raise TypeError("Invalid geometry type")
    return out_geometry, m1, m2

def update_route_location(
        in_features,
        route_layer,
        in_features_route_id_field,
        route_layer_route_id_field,
        measure_field,
        end_measure_field=None,
        rounding_digits=None):
    """Given input features, finds location nearest route.

    Args:
        in_features: Input features to be located. (Feature Layer)
        route_layer: Route layer containing Linear Referencing System (LRS)
        in_features_route_id_field: The field in "in_features" that identifies which route the event is on.
        route_layer_route_id_field: The field in the "route_layer" that contains the unique route identifier.
        measure_field: The field in the input features with begin measures (for lines) or a point's measure (for points).
        end_measure_field: The field in the input features with end measures (for lines). Not used if in_features are points.
        rounding_digits: The number of digits to round to.
    """

    # Convert rounding digits to integer
    if not isinstance(rounding_digits, (int, type(None))):
        rounding_digits = int(rounding_digits)

    # out_rid_field: Name of the route ID field in the output feature class.
    # out_error_field: The name of the new field for error information that will be created in "out_fc".
    # source_oid_field: The name of the source Object ID field in the output feature class.

    out_error_field = "LOC_ERROR"

    route_desc = Describe(route_layer)
    in_features_desc = Describe(in_features)

    if not re.match(r"^(?:(?:Point)|(?:Polyline))$", in_features_desc.shapeType, re.IGNORECASE):
        raise TypeError(
            "Input feature class must be either Point or Polyline.")

    spatial_ref = route_desc.spatialReference

    field_exists, correct_type = field_list_contains(
        in_features_desc.fields, out_error_field)

    if not field_exists:
        arcpy.management.AddField(
            in_features, out_error_field, "STRING", field_alias="Locating Error")
    elif not correct_type:
        arcpy.AddError(
            "Field '%s' already exists in table but is not the correct type." % out_error_field)
    else:
        arcpy.AddWarning(
            "Field '%s' already exists and its data will be overwritten." % out_error_field)

    update_fields = [in_features_route_id_field, "SHAPE@", out_error_field, measure_field]
    if end_measure_field:
        update_fields.append(end_measure_field)

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
                    updated_geometry, m1, m2 = get_measures(event_geometry, route_geometry)
                    if rounding_digits is not None:
                        if m1:
                            m1 = round(m1, rounding_digits)
                        if m2:
                            m2 = round(m2, rounding_digits)
                    # Geometry should not change, so no need to update it.
                    # row[1] = updated_geometry
                    row[2] = None
                    row[3] = m1
                    if end_measure_field:
                        row[4] = m2
                    break
                if not route_geometry:
                    row[2] = "Route not found: %s" % in_route_id
                    error_count += 1
            update_cursor.updateRow(row)

    if error_count:
        arcpy.AddWarning("Unable to locate %d out of %d events." % (error_count, feature_count))
