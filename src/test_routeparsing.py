"""unit test for wsdot.route module
"""
from __future__ import (unicode_literals, print_function, division,
                        absolute_import)

import unittest
from wsdot.route import standardize_route_id, RouteIdSuffixType


class TestRouteIdParsing(unittest.TestCase):
    """Unit tests
    """
    def test_route_id_parsing(self):
        in_id = "I-5"
        expected_out = "005i"
        actual_out = standardize_route_id(
            in_id, RouteIdSuffixType.has_i_suffix | RouteIdSuffixType.has_d_suffix)
        self.assertEqual(expected_out, actual_out)
        # Test default parameters, which should be the same as above
        actual_out = standardize_route_id(in_id)
        self.assertEqual(expected_out, actual_out)


if __name__ == '__main__':
    unittest.main()
