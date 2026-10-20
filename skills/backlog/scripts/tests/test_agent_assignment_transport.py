import io
import unittest
import urllib.error
from contextlib import redirect_stderr
from unittest.mock import patch
import plane_client

class TransportRegressionTests(unittest.TestCase):
    def test_existing_429_transport_has_four_bounded_attempts_without_sleep_or_network(self):
        client = plane_client.PlaneClient(profile=dict(plane_host='https://offline.invalid', token='synthetic-only', workspace_slug='demo'))
        error = urllib.error.HTTPError('https://offline.invalid', 429, 'limited', {}, None)
        self.addCleanup(error.close)
        with patch.object(plane_client.urllib.request, 'urlopen', side_effect=error) as request, \
             patch.object(plane_client.time, 'sleep') as sleep, redirect_stderr(io.StringIO()):
            with self.assertRaises(plane_client.PlaneError): client.request('fixture/')
        self.assertEqual(request.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [65, 30, 30, 30])
        self.assertEqual(request.call_args.args[0].get_header('User-agent'), plane_client.UA)
