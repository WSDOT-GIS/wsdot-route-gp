"""Defines the wsdotroute toolbox.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import sys
import os
import re
import arcpy

from wsdot.route import create_event_feature_class, RouteIdSuffixType


def _create_field(**kwargs):
    field = arcpy.Field()
    field.name = kwargs.get("name")
    field.aliasName = kwargs.get("aliasName")
    field.type = kwargs.get("type")
    return field


def _get_first_field(fields, regex, *typeOrTypes):
    """Returns the first field in a collection of fields that matches the
    given conditions.

    Args:
        fields: An enumeration of arcpy.Field objects.
        regex: A regular expression that will be used to match field name.
            If a str is provided, it will be converted to re with re.IGNORECASE
            option.
        typeOrType: Either a single type or a collection of field type names
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


class _Ords(object):
    """Used to access indexes for parameters
    """
    event_table = 0
    route_layer = 1
    event_table_route_id_field = 2
    route_layer_route_id_field = 3
    begin_measure_field = 4
    end_measure_field = 5
    route_id_suffix = 6
    out_fc = 7


class Toolbox(object):
    def __init__(self):
        '''Define the toolbox (the name of the toolbox is the name of the
        .pyt file).'''
        self.label = 'WSDOT Route'
        self.alias = 'wsdotroute'
        # List of tool classes associated with this toolbox
        self.tools = [LocateRouteEvents]


class LocateRouteEvents(object):
    def __init__(self):
        '''Define the tool (tool name is the name of the class).'''
        self.label = 'LocateRouteEvents'
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
        begin_measure_field_param.filter.list = ['Double', 'Single']
        begin_measure_field_param.parameterDependencies = [
            event_table_param.name]

        end_measure_field_param = arcpy.Parameter(
            "end_m_field", "End Measure Field", "Input", "Field", "Optional"
        )
        end_measure_field_param.filter.list = ['Double', 'Single']
        end_measure_field_param.parameterDependencies = [
            event_table_param.name]

        route_id_suffix_param = arcpy.Parameter(
            "route_id_suffix_type", "Route ID suffix type", "Input",
            "GPString", "Required"
        )
        route_id_suffix_param.filter.type = "ValueList"
        route_id_suffix_param.filter.list = ["NONE", "D_ONLY", "I_ONLY", "ALL"]
        route_id_suffix_param.value = "ALL"

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
            route_id_suffix_param,
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
        event_table_param = parameters[_Ords.event_table]
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

            route_id_field = parameters[_Ords.event_table_route_id_field]
            if not route_id_field.value:
                route_id_field.value = _get_first_field(
                    event_table_desc.fields, route_id_re, "String", "TEXT")

            m_1_field_param = parameters[_Ords.begin_measure_field]
            if not m_1_field_param.value:
                m_1_field_param.value = _get_first_field(
                    event_table_desc.fields, begin_m_re, "Double", "Single")

            m_2_field_param = parameters[_Ords.end_measure_field]
            if not m_2_field_param.value:
                m_2_field_param.value = _get_first_field(
                    event_table_desc.fields, end_m_re, "Double", "Single")

        route_layer_param = parameters[_Ords.route_layer]
        if route_layer_param.altered and route_layer_param.value:
            route_layer_rid_field_param = parameters[_Ords.route_layer_route_id_field]
            if not route_layer_rid_field_param.value:
                route_layer_desc = arcpy.Describe(
                    route_layer_param.valueAsText)
                route_layer_rid_field_param.value = _get_first_field(
                    route_layer_desc.fields, route_id_re, "String", "TEXT")

        end_measure_field_param = parameters[_Ords.end_measure_field]
        if end_measure_field_param.altered:
            out_fc_param = parameters[_Ords.out_fc]
            if end_measure_field_param.value:
                out_fc_param.schema.geometryType = "Polyline"
            else:
                out_fc_param.schema.geometryType = "Point"

        # Warn if user selects field containing "SRMP" for measure field.
        begin_m_p = parameters[_Ords.begin_measure_field]
        end_m_p = parameters[_Ords.end_measure_field]
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
                bad_re = re.compile(r"S(tate)?R(oute)?M(ile)?P(ost)?", re.IGNORECASE)
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
        event_table = parameters[0].valueAsText
        route_layer = parameters[1].valueAsText
        event_table_route_id_field = parameters[2].valueAsText
        route_layer_route_id_field = parameters[3].valueAsText
        begin_measure_field = parameters[4].valueAsText
        end_measure_field = parameters[5].valueAsText
        if end_measure_field == "#":
            end_measure_field = None

        suffix_dict = {
            "NONE": RouteIdSuffixType.has_no_suffix,
            "I_ONLY": RouteIdSuffixType.has_i_suffix,
            "D_ONLY": RouteIdSuffixType.has_d_suffix,
            "ALL": RouteIdSuffixType.has_i_suffix | RouteIdSuffixType.has_d_suffix
        }
        route_id_suffix = suffix_dict[parameters[6].valueAsText]
        out_fc = parameters[7].valueAsText
        create_event_feature_class(event_table, route_layer, event_table_route_id_field,
                                   route_layer_route_id_field, begin_measure_field,
                                   end_measure_field, route_id_suffix, out_fc)
        return
