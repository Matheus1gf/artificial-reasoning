"""Independent analytic and out-of-sample checks of the bounded physics lab."""
import math
import random
import unittest

from src.science import physics, symbolic


class PhysicsTests(unittest.TestCase):
    def test_motion_matches_independent_analytic_reference_and_external_work(self):
        for x, v, a, duration in [(1., 2., 0., .5), (-2., -1., .7, 1.4), (4., .5, -1.5, 1.7)]:
            for steps in (1, 7, 64):
                result = physics.simulate(x, v, duration, a, steps=steps, mass=3.)
                expected_x = x + v * duration + a * duration ** 2 / 2
                expected_v = v + a * duration
                self.assertAlmostEqual(result["x"], expected_x, places=10)
                self.assertAlmostEqual(result["v"], expected_v, places=10)
                self.assertAlmostEqual(result["kinetic_energy_change"], 1.5 * (expected_v ** 2 - v ** 2), places=9)
                self.assertAlmostEqual(result["energy_balance_residual"], 0, places=9)
                self.assertTrue(result["verified"])

    def test_dimensional_analysis_rejects_invalid_sums_and_supports_products(self):
        self.assertEqual(physics.dimension({"op": "multiply", "left": "m/s", "right": "s"}), (1, 0, 0))
        self.assertEqual(physics.dimension({"op": "multiply", "left": "N", "right": "m"}), (2, -2, 1))
        with self.assertRaises(ValueError):
            physics.dimension({"op": "add", "left": "m", "right": "s"})
        with self.assertRaises(ValueError):
            physics.dimension("furlong")

    def test_simulation_rejects_invalid_units_types_bounds_and_nonfinite(self):
        for parameters in ({"x": float("nan")}, {"v": True}, {"dt": 0}, {"a": 3}, {"mass": -1},
                           {"steps": True}, {"steps": 10001}, {"units": {"v": "m"}}, {"units": []}):
            args = dict(x=0, v=1, dt=1)
            args.update(parameters)
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                physics.simulate(**args)

    def test_parameters_learned_from_positions_predict_unseen_time(self):
        x0, v0, acceleration = -.7, 1.3, .4
        position = lambda t: x0 + v0 * t + .5 * acceleration * t * t
        data = [{"t": t, "x": position(t)} for t in (0, .3, .8, 1.2, 1.5)]
        model = physics.fit_motion(data, degree=2)
        self.assertAlmostEqual(model["parameters"]["x0"], x0, places=10)
        self.assertAlmostEqual(model["parameters"]["v0"], v0, places=10)
        self.assertAlmostEqual(model["parameters"]["a"], acceleration, places=10)
        self.assertAlmostEqual(physics.predict_motion(model, 1.8), position(1.8), places=10)
        self.assertTrue(model["compatible"])

    def test_noisy_fit_and_unidentified_design_are_distinguished(self):
        generator = random.Random(56017)
        data = [{"t": i / 10, "x": 1 + 2 * i / 10 + generator.gauss(0, .002)} for i in range(15)]
        model = physics.fit_motion(data, degree=1, noise_sigma=.002)
        self.assertAlmostEqual(model["parameters"]["v0"], 2, delta=.01)
        self.assertTrue(model["compatible"])
        with self.assertRaises(ValueError):
            physics.fit_motion([{"t": 1, "x": i} for i in range(4)], degree=2)

    def test_experiment_retains_refutation_and_revises_a_wrong_model(self):
        position = lambda t: 1 + .4 * t + .7 * t * t
        data = [{"t": t, "x": position(t)} for t in (0, .3, .8, 1.1)]
        result = physics.experiment(data, {"t": 1.7, "x": position(1.7)}, degree=1)
        self.assertTrue(result["refuted"])
        self.assertIsNotNone(result["negative_result"])
        self.assertTrue(result["revised"]["compatible"])
        self.assertAlmostEqual(physics.predict_motion(result["revised"], 1.9), position(1.9), places=9)


class SymbolicDiscoveryTests(unittest.TestCase):
    def test_anonymous_dimensioned_data_recovers_a_product_and_predicts_new_combination(self):
        samples = [{"variables": {"q": q, "r": r}, "target": 2.5 * q * r}
                   for q, r in ((.5, .2), (.8, .9), (1.2, .4), (1.6, 1.1), (2., .7), (2.3, 1.7))]
        model = symbolic.discover(samples, dimensions={"q": [1, -1, 0], "r": [0, 1, 0]},
                                  target_dimension=[1, 0, 0], max_degree=2, max_terms=2)
        self.assertEqual(model["status"], "identified")
        self.assertTrue(model["typed"])
        self.assertAlmostEqual(symbolic.predict(model, {"q": 1.9, "r": 1.3}), 2.5 * 1.9 * 1.3, places=9)

    def test_dimensional_prior_cannot_silently_produce_an_incompatible_equation(self):
        samples = [{"variables": {"q": q}, "target": q * q} for q in (.2, .7, 1.1, 1.5, 1.9)]
        model = symbolic.discover(samples, dimensions={"q": [1, 0, 0]}, target_dimension=[0, 1, 0])
        self.assertEqual(model["status"], "unknown")

    def test_candidate_budget_is_a_real_bound_and_is_reported(self):
        samples = [{"variables": {"u": u}, "target": 3 * u * u + 2 * u + 1} for u in (.1, .5, .9, 1.3, 1.7)]
        model = symbolic.discover(samples, max_candidates=1)
        self.assertEqual(model["candidates_evaluated"], 1)
        self.assertTrue(model["budget_exhausted"])


if __name__ == "__main__":
    unittest.main()
