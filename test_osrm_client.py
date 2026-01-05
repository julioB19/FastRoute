import unittest
from unittest.mock import Mock, patch

import requests

from osrm_client import OSRMClient


class OSRMClientTestCase(unittest.TestCase):
    def setUp(self):
        session_mock = Mock()
        self.client = OSRMClient(base_url="http://localhost:5000", session=session_mock)

    def test_route_success_includes_geometry_and_steps(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 123.4,
                    "duration": 56.7,
                    "geometry": {"type": "LineString", "coordinates": []},
                    "legs": [{"summary": "leg"}],
                }
            ],
        }
        self.client.session.get.return_value = response

        result = self.client.route((10.0, 20.0), (11.0, 21.0), overview="full", geometries="geojson", steps=True)

        called_url = self.client.session.get.call_args[0][0]
        self.assertIn("/route/v1/driving/20.000000,10.000000;21.000000,11.000000", called_url)
        self.assertEqual(result["distance"], 123.4)
        self.assertEqual(result["duration"], 56.7)
        self.assertIn("geometry", result)
        self.assertIn("steps", result)

    def test_table_success_returns_distances_and_durations(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": "Ok",
            "distances": [[0, 10.0], [10.0, 0]],
            "durations": [[0, 100.0], [100.0, 0]],
        }
        self.client.session.get.return_value = response

        result = self.client.table([(0.0, 0.0), (1.0, 1.0)], fallback_to_route=False)

        self.assertEqual(result["distances"][0][1], 10.0)
        self.assertEqual(result["durations"][0][1], 100.0)

    def test_table_fallback_uses_route_loop(self):
        # Forca o _request a falhar e garante que o fallback via /route preenche a matriz.
        self.client.session.get.side_effect = requests.Timeout()
        with patch.object(OSRMClient, "route", return_value={"distance": 50.0, "duration": 25.0}) as route_mock:
            result = self.client.table([(0.0, 0.0), (1.0, 1.0)])

        route_mock.assert_called()  # confirmou uso do fallback
        self.assertEqual(result["distances"][0][1], 50.0)
        self.assertEqual(result["durations"][0][1], 25.0)


if __name__ == "__main__":
    unittest.main()
