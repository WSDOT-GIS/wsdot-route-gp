"""Utilities for parsing WSDOT state route IDs.
Code contained herein does not require arcpy.
"""

from __future__ import absolute_import, division, print_function, unicode_literals
import re

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
            See the RouteIdSuffixType values. Defaults to RouteIdSuffixType.has_both_i_and_d.

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
