"""Defines the wsdotroute toolbox.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import sys
import os
import arcpy

# Update path to insure toolbox can find wsdotroute module.
_NEW_PATH = os.path.join(os.path.split(__file__)[0], "../../..")
_NEW_PATH = os.path.abspath(_NEW_PATH)
sys.path.append(os.path.abspath(_NEW_PATH))
del _NEW_PATH

from wsdotroute import create_event_feature_class

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
        self.canRunInBackground = False

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
        begin_measure_field_param.filter.list = ['Double']
        begin_measure_field_param.parameterDependencies = [
            event_table_param.name]

        end_measure_field_param = arcpy.Parameter(
            "end_m_field", "End Measure Field", "Input", "Field", "Optional"
        )
        end_measure_field_param.filter.list = ['Double']
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
