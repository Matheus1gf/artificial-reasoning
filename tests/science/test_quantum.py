"""Independent Born-rule, unitary, inference and classical-control checks."""
import math
import random
import unittest

from src.science import quantum


class QuantumTests(unittest.TestCase):
    def test_hadamard_and_pauli_gates_match_known_states(self):
        plus = quantum.apply_unitary([1, 0], quantum.H)
        self.assertAlmostEqual(plus[0].real, math.sqrt(.5), places=12)
        self.assertAlmostEqual(plus[1].real, math.sqrt(.5), places=12)
        restored = quantum.apply_unitary(plus, quantum.H)
        self.assertAlmostEqual(abs(restored[0] - 1), 0, places=12)
        self.assertAlmostEqual(abs(restored[1]), 0, places=12)
        self.assertEqual(quantum.apply_unitary([1, 0], quantum.X), [0j, 1 + 0j])
        self.assertAlmostEqual(quantum.expectation(plus, quantum.X), 1, places=12)
        self.assertAlmostEqual(quantum.expectation(plus, quantum.Z), 0, places=12)

    def test_complex_phases_born_rule_and_hermitian_expectation(self):
        state = [math.sqrt(.3), 1j * math.sqrt(.7)]
        probabilities = quantum.born_probabilities(state)
        self.assertAlmostEqual(probabilities[0], .3, places=12)
        self.assertAlmostEqual(probabilities[1], .7, places=12)
        self.assertAlmostEqual(quantum.expectation(state, quantum.Z), -.4, places=12)
        with self.assertRaises(ValueError):
            quantum.expectation([1, 0], [[0, 1], [0, 0]])

    def test_rx_evolution_and_inverse_preserve_norm(self):
        omega, duration = .9, 1.3
        state = quantum.evolve([1, 0], omega, duration)
        self.assertAlmostEqual(state[0].real, math.cos(omega * duration / 2), places=12)
        self.assertAlmostEqual(state[1].imag, -math.sin(omega * duration / 2), places=12)
        back = quantum.apply_unitary(state, quantum.rotation_x(-omega * duration))
        self.assertAlmostEqual(abs(back[0] - 1), 0, places=12)
        self.assertAlmostEqual(abs(back[1]), 0, places=12)
        self.assertAlmostEqual(sum(quantum.born_probabilities(state)), 1, places=12)

    def test_invalid_states_operators_and_resources_are_rejected(self):
        for state in ([0, 0], [1, 1], [1, 0, 0], [float("nan"), 0], [True, 0]):
            with self.subTest(state=state), self.assertRaises(ValueError):
                quantum.born_probabilities(state)
        with self.assertRaises(ValueError):
            quantum.apply_unitary([1, 0], [[1, 1], [0, 1]])
        with self.assertRaises(ValueError):
            quantum.measure([1, 0], shots=True)
        with self.assertRaises(ValueError):
            quantum.state_cost(9)

    def test_sampling_reproducibility_frequencies_and_no_global_rng_mutation(self):
        before = random.getstate()
        state = [math.sqrt(.25), math.sqrt(.75)]
        result = quantum.measure(state, shots=10000, seed=78017)
        self.assertEqual(result, quantum.measure(state, shots=10000, seed=78017))
        self.assertEqual(sum(result["counts"]), 10000)
        self.assertAlmostEqual(result["counts"][0] / 10000, .25, delta=.02)
        self.assertEqual(before, random.getstate())

    def test_frequency_is_learned_from_counts_and_ambiguity_is_preserved(self):
        times = (.4, 1.1, 1.8)
        observations = [{"t": t, "shots": 10000, "zeros": round(10000 * math.cos(.8 * t / 2) ** 2)} for t in times]
        fitted = quantum.fit_frequency(observations, candidates=[.3, .8, 1.4])
        self.assertEqual(fitted["omega"], .8)
        self.assertFalse(fitted["ambiguous"])
        ambiguous = quantum.fit_frequency([{"t": 0, "shots": 100, "zeros": 100}], candidates=[.3, .8, 1.4])
        self.assertTrue(ambiguous["ambiguous"])
        self.assertEqual(set(ambiguous["plausible_candidates"]), {.3, .8, 1.4})

    def test_measurement_choice_prefers_a_discriminating_time(self):
        choice = quantum.choose_measurement([0, math.pi], [0, 1])
        self.assertEqual(choice["selected"]["t"], 1)
        self.assertTrue(choice["informative"])
        self.assertFalse(quantum.choose_measurement([.3, .8], [0])["informative"])

    def test_context_quantum_and_classical_controls_have_equivalent_predictions(self):
        for theta, phi in ((.2, .7), (.8, .4), (1.1, 1.2)):
            for order in ("AB", "BA"):
                total = 0
                for first in (0, 1):
                    for second in (0, 1):
                        q = quantum.sequential_probability(theta, phi, order, first, second)
                        c = quantum.classical_context_probability(theta, phi, order, first, second)
                        self.assertAlmostEqual(q, c, places=12)
                        total += q
                self.assertAlmostEqual(total, 1, places=12)

    def test_context_fit_uses_the_same_parameter_budget_for_both_models(self):
        observations = [{"order": "AB", "counts": [60, 10, 5, 25]},
                        {"order": "BA", "counts": [40, 15, 10, 35]}]
        q = quantum.contextual_fit(observations, "quantum", grid_size=7)
        c = quantum.contextual_fit(observations, "classical_context", grid_size=7)
        self.assertEqual(q["free_parameters"], c["free_parameters"])
        self.assertEqual(q["grid_evaluations"], c["grid_evaluations"])
        self.assertAlmostEqual(q["nll"], c["nll"], places=9)

    def test_state_cost_reports_exponential_amplitudes_without_claiming_python_rss(self):
        for qubits in (1, 4, 8):
            result = quantum.state_cost(qubits, repeats=2)
            self.assertEqual(result["amplitudes"], 2 ** qubits)
            self.assertEqual(result["complex128_payload_bytes"], 16 * 2 ** qubits)
            self.assertIn("overhead", result["python_storage_note"])
            self.assertGreaterEqual(result["elapsed_seconds"], 0)
            self.assertAlmostEqual(result["normalization_error"], 0, places=12)


if __name__ == "__main__":
    unittest.main()
