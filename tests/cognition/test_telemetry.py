"""Resource reporting distinguishes verified solutions, lifetime RSS and unavailable values."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.cognition.contracts import AnswerPackage, ProblemSpec
from src.cognition import telemetry


class TelemetryTests(unittest.TestCase):
    def package(self,status='answered',checks=None):
        return AnswerPackage.build(ProblemSpec.build('Calcule 3*2.'),status,['Resultado do núcleo.'],verification=[] if checks is None else checks)

    def test_validated_cost_uses_real_times_and_declares_memory_scope(self):
        package=self.package(checks=[{'check':'arithmetic','passed':True}])
        fake=SimpleNamespace(RUSAGE_SELF=0,getrusage=lambda _:SimpleNamespace(ru_maxrss=512))
        with patch.object(telemetry,'resource',fake),patch.object(telemetry.sys,'platform','linux'),patch.object(telemetry.time,'perf_counter',side_effect=[10,12]),patch.object(telemetry.time,'process_time',side_effect=[2,2.5]):
            result=telemetry.finish_measurement(telemetry.start_measurement(),package)
        self.assertEqual(result['wall_seconds'],2)
        self.assertEqual(result['cpu_seconds'],.5)
        self.assertEqual(result['process_peak_rss_bytes'],512*1024)
        self.assertEqual(result['wall_seconds_per_verified_solution'],2)
        self.assertIsNone(result['monetary_cost'])
        self.assertIn('process lifetime',result['memory_scope'])
        self.assertIn('before final persistence',result['measurement_scope'])

    def test_unknown_incomplete_and_failed_checks_are_not_counted_as_valid_solutions(self):
        for status,checks in [('unknown',[{'passed':True}]),('answered',[]),('answered',[{'passed':False}]),('answered',[{'passed':True},{'passed':False}])]:
            with self.subTest(status=status,checks=checks),patch.object(telemetry,'resource',None):
                result=telemetry.finish_measurement(telemetry.start_measurement(),self.package(status,checks))
                self.assertFalse(result['verified_solution'])
                self.assertIsNone(result['wall_seconds_per_verified_solution'])
                self.assertIsNone(result['process_peak_rss_bytes'])

    def test_macos_rss_is_bytes_without_linux_conversion(self):
        fake=SimpleNamespace(RUSAGE_SELF=0,getrusage=lambda _:SimpleNamespace(ru_maxrss=2048))
        with patch.object(telemetry,'resource',fake),patch.object(telemetry.sys,'platform','darwin'):
            result=telemetry.finish_measurement(telemetry.start_measurement(),self.package())
        self.assertEqual(result['process_peak_rss_bytes'],2048)


if __name__=='__main__':unittest.main()
