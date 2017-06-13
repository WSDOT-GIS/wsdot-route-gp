"""Dumps a feature class to a CSV file.
"""
from __future__ import (
    unicode_literals, absolute_import, division, print_function)

import argparse
import base64
import csv
import os
import re
import datetime
from sys import stdout
import arcpy


def dump_fc(fc_path, out_file):
    """Dumps a feature class to a CSV file.
    """
    if not arcpy.Exists(fc_path):
        # Exit with "{x} does not exist message."
        msg = arcpy.AddIDMessage("ERROR", 110, fc_path)
        raise FileNotFoundError(msg)

    # Create a list of the fields for cursor
    fc_desc = arcpy.Describe(fc_path)
    field_list = []
    skip_re = re.compile("Shape_Length", re.IGNORECASE)
    has_geometry = False
    for field in fc_desc.fields:
        if skip_re.match(field.name) or field.type == "OID":
            continue
        elif field.type == "Geometry":
            has_geometry = True
        else:
            field_list.append(field.name)
    if has_geometry:
        field_list.append("SHAPE@WKB")

    try:
        file_obj = None
        if out_file:
            file_obj = open(out_file, 'w', newline='')

        if file_obj:
            csv_writer = csv.writer(file_obj)
        else:
            csv_writer = csv.writer(stdout)
        csv_writer.writerow(field_list)
        with arcpy.da.SearchCursor(fc_path, field_list) as cursor:
            def prepare_for_csv(item):
                """Converts a data item to a format that can be written to CSV.
                """
                if isinstance(item, bytearray):
                    return base64.b64encode(item).decode(encoding='utf-8')
                elif isinstance(item, datetime.datetime):
                    return item.date()
                else:
                    return item

            for row in cursor:
                csv_writer.writerow(map(prepare_for_csv, row))
            del row

    finally:
        if file_obj:
            file_obj.flush()
            file_obj.close()




if __name__ == '__main__':
    ARG_PARSER = argparse.ArgumentParser(description=__doc__)
    ARG_PARSER.add_argument("feature_class_path",
                            help="Path to a feature class")
    ARG_PARSER.add_argument("output_file",
                            help="Path where the output data will be written to as text. " +
                            "If omitted, output will be written to console.",
                            nargs='?')
    args = ARG_PARSER.parse_args()

    dump_fc(args.feature_class_path, args.output_file)
