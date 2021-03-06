"""Defines the wsdotroute toolbox.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import re
import arcpy

# pylint:disable=import-self,invalid-name,no-self-use,unused-argument,too-few-public-methods


try:
    from wsdotroute import (add_standardized_route_id_field,
                            create_event_feature_class,
                            update_route_location,
                            points_to_line_events,
                            points_to_line_event_features,
                            RouteIdSuffixType)
except ImportError:
    from sys import path
    from os.path import abspath, dirname, join as join_path
    path.append(
        abspath(
            join_path(
                dirname(__file__),
                *("..",) * 3
            )
        )
    )
    from wsdotroute import (add_standardized_route_id_field,
                            create_event_feature_class,
                            update_route_location,
                            points_to_line_events,
                            points_to_line_event_features,
                            RouteIdSuffixType)


_suffix_dict = {
    "NONE": RouteIdSuffixType.has_no_suffix,
    "I_ONLY": RouteIdSuffixType.has_i_suffix,
    "D_ONLY": RouteIdSuffixType.has_d_suffix,
    "ALL": RouteIdSuffixType.has_i_suffix | RouteIdSuffixType.has_d_suffix
}


def _create_field(**kwargs):
    field = arcpy.Field()
    if "name" in kwargs:
        field.name = kwargs["name"]
    if "aliasName" in kwargs:
        field.aliasName = kwargs["aliasName"]
    if "type" in kwargs:
        field.type = kwargs["type"]
    return field


def _get_first_field(fields, regex, *typeOrTypes):
    """Returns the first field in a collection of fields that matches the
    given conditions.

    Args:
        fields: An enumeration of arcpy.Field objects.
        regex: A regular expression that will be used to match field name.
            If a str is provided, it will be converted to re with re.IGNORECASE
            option.
        typeOrTypes: Either a single type or a collection of field type names
    Returns:
        Returns the first field matching the given conditions, or None if
        there are no matches.
    """
    for field in fields:
        if isinstance(regex, str):
            regex = re.compile(regex, re.IGNORECASE)
        if regex.match(field.name) and field.type in typeOrTypes:
            return field.name
    return None


class _LocateRouteEventsOrds(object):
    """Used to access indexes for parameters
    """
    event_table = 0
    route_layer = 1
    event_table_route_id_field = 2
    route_layer_route_id_field = 3
    begin_measure_field = 4
    end_measure_field = 5
    out_fc = 6


class Toolbox(object):
    """Defines the toolbox
    """
    def __init__(self):
        '''Define the toolbox (the name of the toolbox is the name of the
        .pyt file).'''
        self.label = 'WSDOT Route'
        self.alias = 'wsdotroute'
        # List of tool classes associated with this toolbox
        self.tools = [LocateRouteEvents,
                      AddDirectionedRouteIdField, UpdateRouteLocation,
                      PointsToLineEvents, PointsToLineEventFeatures]


class AddDirectionedRouteIdField(object):
    """Defines the Add directioned route ID field tool.
    """
    def __init__(self):
        """Initializes the tool
        """
        self.label = 'Add directioned route ID field'
        self.descripiton = 'Adds a new field that combines WSDOT route ID and direction.'
        self.canRunInBackground = True

    def getParameterInfo(self):
        """Defines the tool's parameters
        """
        table_param = arcpy.Parameter(
            "in_table", "In Table", "Input", "DETable", "Required")
        route_id_field_param = arcpy.Parameter("route_id_field", "Route ID Field", "Input",
                                               "Field", "Required")
        route_id_field_param.parameterDependencies = [table_param.name]
        route_id_field_param.filter.list = ['Text']

        direction_field_param = arcpy.Parameter("direction_field", "Direction Field", "Input",
                                                "Field", "Required")
        direction_field_param.parameterDependencies = [table_param.name]
        direction_field_param.filter.list = ['Text']

        out_route_id_field_name_param = arcpy.Parameter(
            "out_route_id_field_name", "Output route ID field name",
            "Input", "String", "Required"
        )
        out_error_field_name_param = arcpy.Parameter(
            "out_error_field_name", "Output Error Field Name", "Input", "String", "Required")

        out_route_id_suffix_type_param = arcpy.Parameter("route_id_suffix_type",
                                                         "Route ID Suffix Type", "Input",
                                                         "String", "Required")
        out_route_id_suffix_type_param.filter.type = "ValueList"
        out_route_id_suffix_type_param.filter.list = [
            "D_ONLY", "I_ONLY", "ALL"]
        out_route_id_suffix_type_param.value = "ALL"

        wsdot_validate_param = arcpy.Parameter(
            "wsdot_validate", "Perform WSDOT Route ID validation?", "Input", "Boolean", "Optional")
        wsdot_validate_param.value = True

        out_table_param = arcpy.Parameter("out_table", "Output Table", "Output",
                                          "DETable", "Derived")
        out_table_param.parameterDependencies = [table_param.name]
        out_table_param.schema.clone = True

        return [
            table_param,
            route_id_field_param,
            direction_field_param,
            out_route_id_field_name_param,
            out_error_field_name_param,
            out_route_id_suffix_type_param,
            wsdot_validate_param,
            out_table_param
        ]

    def isLicensed(self):
        '''Set whether tool is licensed to execute.'''
        return True

    def updateParameters(self, parameters):
        '''Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed.'''
        # Update output schema when new field name parameters have values.
        out_route_id_field_name_param, out_error_field_name_param = parameters[3:5]
        out_table_param = parameters[-1]

        if out_error_field_name_param.altered or out_route_id_field_name_param.altered:
            new_fields = []
            if out_route_id_field_name_param.valueAsText:
                new_fields.append(_create_field(
                    name=out_route_id_field_name_param.valueAsText, type="String"))
            if out_error_field_name_param.valueAsText:
                new_fields.append(_create_field(
                    name=out_error_field_name_param.valueAsText, type="String"))
            out_table_param.schema.additionalFields = new_fields

        # TODO: Make sure new field names are valid and don't already exist in table.

        return

    def updateMessages(self, parameters):
        '''Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation.'''
        return

    def execute(self, parameters, messages):
        '''The source code of the tool.'''
        # Get the text values of these parameters and assign to variables.
        # Do this for all but the last two parameters, which will be handled
        # differently.
        table, route_id_field, direction_field, out_route_id_field, out_error_field = map(
            lambda p: p.valueAsText, parameters[:5])

        out_route_id_suffix_type = _suffix_dict[parameters[5].valueAsText]
        wsdot_validate = parameters[6].value

        add_standardized_route_id_field(
            table, route_id_field, direction_field, out_route_id_field, out_error_field, out_route_id_suffix_type, wsdot_validate)

        return


class LocateRouteEvents(object):
    """Defines the Locate Route Events tool.
    """
    def __init__(self):
        '''Define the tool (tool name is the name of the class).'''
        self.label = 'Locate Route Events'
        self.description = 'Locates route events along Washington state routes'
        self.canRunInBackground = True

    def getParameterInfo(self):
        '''Define parameter definitions'''
        event_table_param = arcpy.Parameter(
            "event_table", "Event Table", "Input", "GPTableView", "Required")

        route_layer_param = arcpy.Parameter(
            "route_layer", "Route Layer", "Input", "GPFeatureLayer", "Required")
        route_layer_param.filter.list = ["Polyline"]

        event_table_route_id_field_param = arcpy.Parameter(
            "event_table_route_id_field", "Event Table Route ID Field",
            "Input", "Field", "Required"
        )
        event_table_route_id_field_param.filter.list = ['Text']
        event_table_route_id_field_param.parameterDependencies = [
            event_table_param.name]

        route_layer_route_id_field_param = arcpy.Parameter(
            "route_layer_route_id_field", "Route Layer Route ID Field",
            "Input", "Field", "Required"
        )
        route_layer_route_id_field_param.filter.list = ['Text']
        route_layer_route_id_field_param.parameterDependencies = [
            route_layer_param.name]

        begin_measure_field_param = arcpy.Parameter(
            "begin_m_field", "Begin Measure Field", "Input", "Field", "Required"
        )
        begin_measure_field_param.filter.list = ['Float', 'Double', 'Single']
        begin_measure_field_param.parameterDependencies = [
            event_table_param.name]

        end_measure_field_param = arcpy.Parameter(
            "end_m_field", "End Measure Field", "Input", "Field", "Optional"
        )
        end_measure_field_param.filter.list = ['Float', 'Double', 'Single']
        end_measure_field_param.parameterDependencies = [
            event_table_param.name]

        out_fc_param = arcpy.Parameter(
            "out_fc", "Output Feature Class", "Output", "DEFeatureClass", "Required"
        )
        out_fc_param.schema.geometryTypeRule = "AsSpecified"
        out_fc_param.schema.geometryType = "Point"
        out_fc_param.schema.fieldsRule = "None"
        out_fc_param.schema.additionalFields = [
            _create_field(**{
                "name": "EventOid",
                "aliasName": "Event OID",
                "type": "Integer"
            }),
            _create_field(**{
                "name": "Error",
                "aliasName": "Locating Error",
                "type": "String"
            })
        ]

        params = [
            event_table_param,
            route_layer_param,
            event_table_route_id_field_param,
            route_layer_route_id_field_param,
            begin_measure_field_param,
            end_measure_field_param,
            out_fc_param
        ]
        return params

    def isLicensed(self):
        '''Set whether tool is licensed to execute.'''
        return True

    def updateParameters(self, parameters):
        '''Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed.'''
        event_table_param = parameters[_LocateRouteEventsOrds.event_table]
        re_options = re.IGNORECASE | re.VERBOSE
        route_id_re = re.compile(r"R(?:oute)?Id(?:entifier)?")
        begin_m_re = re.compile(r"""((Begin)|(Start))?(
                (?:ARM)|
                (?:M(easure)?)
            )""", re_options)
        end_m_re = re.compile(r"""((End)|(Stop))?(
                (?:ARM)|
                (?:M(easure)?)
            )""", re_options)
        # Try to auto-select fields based on their names and types
        if event_table_param.altered and event_table_param.valueAsText:
            event_table_desc = arcpy.Describe(event_table_param.valueAsText)

            route_id_field = parameters[_LocateRouteEventsOrds.event_table_route_id_field]
            if not route_id_field.value:
                route_id_field.value = _get_first_field(
                    event_table_desc.fields, route_id_re, "String", "TEXT")

            m_1_field_param = parameters[_LocateRouteEventsOrds.begin_measure_field]
            if not m_1_field_param.value:
                m_1_field_param.value = _get_first_field(
                    event_table_desc.fields, begin_m_re, "Double", "Single")

            m_2_field_param = parameters[_LocateRouteEventsOrds.end_measure_field]
            if not m_2_field_param.value:
                m_2_field_param.value = _get_first_field(
                    event_table_desc.fields, end_m_re, "Double", "Single")

        route_layer_param = parameters[_LocateRouteEventsOrds.route_layer]
        if route_layer_param.altered and route_layer_param.value:
            route_layer_rid_field_param = parameters[_LocateRouteEventsOrds.route_layer_route_id_field]
            if not route_layer_rid_field_param.value:
                route_layer_desc = arcpy.Describe(
                    route_layer_param.valueAsText)
                route_layer_rid_field_param.value = _get_first_field(
                    route_layer_desc.fields, route_id_re, "String", "TEXT")

        end_measure_field_param = parameters[_LocateRouteEventsOrds.end_measure_field]
        if end_measure_field_param.altered:
            out_fc_param = parameters[_LocateRouteEventsOrds.out_fc]
            if end_measure_field_param.value:
                out_fc_param.schema.geometryType = "Polyline"
            else:
                out_fc_param.schema.geometryType = "Point"

        # Warn if user selects field containing "SRMP" for measure field.
        begin_m_p = parameters[_LocateRouteEventsOrds.begin_measure_field]
        end_m_p = parameters[_LocateRouteEventsOrds.end_measure_field]
        if begin_m_p.altered or end_m_p.altered:
            # Add error message if both parameters are set to the same field.
            if (begin_m_p.valueAsText and end_m_p.valueAsText and
                    begin_m_p.valueAsText == end_m_p.valueAsText):
                end_m_p.setErrorMessage(
                    "'%s' and '%s' cannot both be set to the same field" % (
                        begin_m_p.name,
                        end_m_p.name
                    ))
            else:
                bad_re = re.compile(
                    r"S(tate)?R(oute)?M(ile)?P(ost)?", re.IGNORECASE)
                for p in filter(lambda p: p.value is not None, (begin_m_p, end_m_p)):
                    p.clearMessage()
                    if bad_re.search(p.valueAsText):
                        p.setWarningMessage(
                            "State Route Milepost (SRMP) values are not measures " +
                            "and will not return accurate route event geometry when used.")

        return

    def updateMessages(self, parameters):
        '''Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation.'''

        return

    def execute(self, parameters, messages):
        '''The source code of the tool.'''
        # Get parameter values
        (
            event_table,
            route_layer,
            event_table_route_id_field,
            route_layer_route_id_field,
            begin_measure_field,
            end_measure_field,
            out_fc
        ) = map(lambda p: p.valueAsText, parameters)

        if end_measure_field == "#":
            end_measure_field = None

        create_event_feature_class(event_table, route_layer, event_table_route_id_field,
                                   route_layer_route_id_field, begin_measure_field,
                                   end_measure_field, out_fc)
        return


class UpdateRouteLocation(object):
    """Defines the Update route location tool"""
    def __init__(self):
        '''Define the tool (tool name is the name of the class).'''
        self.label = 'Update route location'
        self.description = 'Updates route geometry'
        self.canRunInBackground = True

    def getParameterInfo(self):
        '''Define parameter definitions'''
        in_features_param = arcpy.Parameter("in_features", "Input Features", "Input",
                                            "GPFeatureLayer", "Required")
        in_features_param.filter.list = ["Point", "Polyline"]

        route_layer_param = arcpy.Parameter("route_layer", "Route Layer", "Input",
                                            "GPFeatureLayer", "Required")
        route_layer_param.filter.list = ["Polyline"]

        in_features_route_id_field_param = arcpy.Parameter(
            "in_features_route_id_field",
            "Input Features Route ID Field",
            "Input", "Field", "Required")
        in_features_route_id_field_param.parameterDependencies = [
            in_features_param.name]
        in_features_route_id_field_param.filter.list = ["TEXT"]

        route_layer_route_id_field_param = arcpy.Parameter(
            "route_layer_route_id_field",
            "Route Layer Route ID Field",
            "Input", "Field", "Required")
        route_layer_route_id_field_param.filter.list = [
            "TEXT"
        ]
        route_layer_route_id_field_param.parameterDependencies = [
            route_layer_param.name]

        measure_field_param = arcpy.Parameter(
            "measure_field", "Measure Field", "Input", "Field", "Required")
        measure_field_2_param = arcpy.Parameter(
            "end_measure_field", "End Measure Field", "Input", "Field", "Optional")

        for p in (measure_field_param, measure_field_2_param):
            p.parameterDependencies = [in_features_param.name]
            p.filter.list = [
                "FLOAT",
                "DOUBLE",
                "SINGLE"
            ]

        rounding_digits_param = arcpy.Parameter(
            "rounding_digits", "Number of digits for rounding", "Input", "Long", "Optional")
        rounding_digits_param.value = 3

        use_m_from_route_point_param = arcpy.Parameter(
            "use_m_from_route_point", "Use M from route point", "Input", "Boolean", "Optional"
        )
        use_m_from_route_point_param.value = True

        out_fc_param = arcpy.Parameter("out_fc", "Output Feature Class", "Output",
                                       "DEFeatureClass", "Derived")

        out_fc_param.parameterDependencies = [in_features_param.name]
        out_fc_param.schema.clone = True


        return [
            in_features_param,
            route_layer_param,
            in_features_route_id_field_param,
            route_layer_route_id_field_param,
            measure_field_param,
            measure_field_2_param,
            rounding_digits_param,
            use_m_from_route_point_param,
            out_fc_param,
        ]

    def isLicensed(self):
        '''Set whether tool is licensed to execute.'''
        return True

    def updateParameters(self, parameters):
        '''Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed.'''
        return

    def updateMessages(self, parameters):
        '''Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation.'''
        return

    def execute(self, parameters, messages):
        '''The source code of the tool.'''
        update_route_location(*map(lambda p: p.valueAsText, parameters[:-1]))
        return


class PointsToLineEvents(object):
    """Defines the Points to Line Events tool.
    """
    def __init__(self):
        '''Define the tool (tool name is the name of the class).'''
        self.label = 'Points to Line Events'
        self.description = ''
        self.canRunInBackground = True

    def getParameterInfo(self):
        '''Define parameter definitions'''
        # in_features_param = arcpy.Parameter(
        #     'in_features', "Input Features", "Input", "GPFeatureRecordSetLayer", "Required")
        # in_features_param.value = join_path(dirname(__file__), "PointFeaturesTemplate.lyr")

        in_features_param = arcpy.Parameter(
            'in_features', "Input Features", "Input", "GPFeatureLayer", "Required")
        in_features_param.filter.list = ["Point"]

        in_routes_param = arcpy.Parameter(
            "in_routes", "Route Layer", "Input", "GPFeatureLayer", "Required")
        route_id_field_param = arcpy.Parameter(
            "route_id_field", "Route ID Field", "Input", "Field", "Required")
        route_id_field_param.parameterDependencies = [in_routes_param.name]

        radius_param = arcpy.Parameter(
            "radius", "Radius", "Input", "GPLinearUnit", "Required")
        # radius_param.valueAsText = "50 FEET"

        out_table_param = arcpy.Parameter(
            "out_table", "Output Table", "Output", "DETable", "Required")
        # out_table_param.valueAsText = arcpy.CreateUniqueName(
        #     "LineEvents", arcpy.env.scratchGDB)

        params = [in_features_param, in_routes_param,
                  route_id_field_param, radius_param, out_table_param]
        return params

    def isLicensed(self):
        '''Set whether tool is licensed to execute.'''
        return True

    def updateParameters(self, parameters):
        '''Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed.'''
        return

    def updateMessages(self, parameters):
        '''Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation.'''
        return

    def execute(self, parameters, messages):
        '''The source code of the tool.'''
        points_to_line_events(*map(lambda p: p.valueAsText, parameters))
        return


class PointsToLineEventFeatures(object):
    """Defines the Points to Line Event features tool.
    """
    def __init__(self):
        '''Define the tool (tool name is the name of the class).'''
        self.label = 'Points to Line Event Features'
        self.description = ''
        self.canRunInBackground = True

    def getParameterInfo(self):
        '''Define parameter definitions'''
        # in_features_param = arcpy.Parameter(
        #     'in_features', "Input Features", "Input", "GPFeatureRecordSetLayer", "Required")
        # in_features_param.value = join_path(dirname(__file__), "PointFeaturesTemplate.lyr")

        in_features_param = arcpy.Parameter(
            'in_features', "Input Features", "Input", "GPFeatureLayer", "Required")
        in_features_param.filter.list = ["Point"]

        in_routes_param = arcpy.Parameter(
            "in_routes", "Route Layer", "Input", "GPFeatureLayer", "Required")
        route_id_field_param = arcpy.Parameter(
            "route_id_field", "Route ID Field", "Input", "Field", "Required")
        route_id_field_param.parameterDependencies = [in_routes_param.name]

        radius_param = arcpy.Parameter(
            "radius", "Radius", "Input", "GPLinearUnit", "Required")
        # radius_param.valueAsText = "50 FEET"

        out_table_param = arcpy.Parameter(
            "out_feature_class", "Output Feature Class", "Output", "DEFeatureClass", "Required")

        params = [in_features_param, in_routes_param,
                  route_id_field_param, radius_param, out_table_param]
        return params

    def isLicensed(self):
        '''Set whether tool is licensed to execute.'''
        return True

    def updateParameters(self, parameters):
        '''Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed.'''
        return

    def updateMessages(self, parameters):
        '''Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation.'''
        return

    def execute(self, parameters, messages):
        '''The source code of the tool.'''
        points_to_line_event_features(
            *map(lambda p: p.valueAsText, parameters))
        return
