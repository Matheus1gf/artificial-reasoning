"""Independent properties of the F00 research fixtures, using QA seeds only."""
import copy
from collections import Counter
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest

from src.research.baselines import BASELINES, symbolic_search
from src.research.worlds import (
    FAMILIES, FAMILY_SIGNATURES, generate_case, hidden_success, observed_success,
)


ROOT = Path(__file__).resolve().parents[2]
QA_SEEDS = (23017, 91307, 401287)


def independent_supported_plans(public):
    """Enumerate tiny plans, independently of the implementation's BFS/checker."""
    question = public["question"]
    successful = []
    for length in range(question["max_steps"] + 1):
        for actions in itertools.product(public["actions"], repeat=length):
            state = question["initial"]
            valid = True
            for action in actions:
                found = [o["after"] for o in public["observations"]
                         if o["before"] == state and o["action"] == action]
                if not found or any(candidate != found[0] for candidate in found):
                    valid = False
                    break
                state = found[0]
            if valid and state == question["goal"]:
                successful.append(list(actions))
    return successful


class WorldProperties(unittest.TestCase):
    def test_reserved_family_constructor_only_with_separate_qa_seeds(self):
        # Exercise the code branch using seeds absent from the scientific
        # protocol. No comparator, score, learning or reserved benchmark runs.
        for seed, index, budget in itertools.product(QA_SEEDS, range(3), (4, 16)):
            case = generate_case("reserved", seed, index, budget)
            self.assertEqual(case.metadata["family"], "coupled_transfer")
            self.assertEqual(len(case.public["objects"]), 2)
            self.assertEqual(len(case.public["observations"]), budget)
            changes = []
            for transition in case.oracle["hidden_transitions"]:
                before, after = transition["before"], transition["after"]
                self.assertEqual(set(before), set(case.public["objects"]))
                self.assertEqual(set(after), set(case.public["objects"]))
                self.assertTrue(all(type(value) is int and value >= 0 for value in before.values()))
                self.assertTrue(all(type(value) is int and value >= 0 for value in after.values()))
                self.assertEqual(sum(before.values()), sum(after.values()))
                changes.append(sum(before[obj] != after[obj] for obj in before))
            self.assertEqual(max(changes), 2)
            for observation in case.public["observations"]:
                self.assertIn(observation, case.oracle["hidden_transitions"])
            public = case.public_input()
            self.assertNotIn("oracle", public)
            self.assertNotIn("metadata", public)
            public["question"]["initial"].clear()
            self.assertEqual(len(case.public["question"]["initial"]), 2)

    def test_rule_structures_vary_beyond_renaming_within_each_exercised_split(self):
        for split in ("development", "validation"):
            signatures = set()
            for seed, index in itertools.product(QA_SEEDS, range(9)):
                case = generate_case(split, seed, index)
                effective = [edge for edge in case.oracle["hidden_transitions"]
                             if edge["before"] != edge["after"]]
                undirected_edges = {frozenset((json.dumps(edge["before"], sort_keys=True),
                                              json.dumps(edge["after"], sort_keys=True)))
                                    for edge in effective}
                # Counts of graph edges and action multiplicities survive every
                # consistent renaming of states, objects and actions.
                multiplicities = tuple(sorted(Counter(edge["action"] for edge in effective).values()))
                signatures.add((len(undirected_edges), multiplicities))
            self.assertGreater(len(signatures), 1, "Changing only names does not vary the rule structure.")

    def test_validation_rules_depend_on_the_other_objects_context(self):
        for seed in QA_SEEDS:
            case = generate_case("validation", seed, 1)
            rules = case.oracle["hidden_transitions"]
            witnessed_guard = False
            for effect in rules:
                changed = [obj for obj in case.public["objects"] if effect["before"][obj] != effect["after"][obj]]
                if len(changed) != 1:
                    continue
                obj = changed[0]
                for other in rules:
                    if (effect["action"] == other["action"]
                            and effect["before"][obj] == other["before"][obj]
                            and effect["before"] != other["before"]
                            and effect["after"][obj] != other["after"][obj]):
                        witnessed_guard = True
            self.assertTrue(witnessed_guard, "The validation family needs a genuine contextual precondition.")

    def test_splits_have_distinct_structural_contracts(self):
        self.assertEqual(set(FAMILIES), {"development", "validation", "reserved"})
        self.assertEqual(len(set(FAMILIES.values())), 3)
        signatures = [json.dumps(FAMILY_SIGNATURES[f], sort_keys=True) for f in FAMILIES.values()]
        self.assertEqual(len(set(signatures)), 3)
        # The dedicated constructor test above checks reserved with QA seeds;
        # capability comparisons below exercise development/validation only.
        for split in ("development", "validation"):
            case = generate_case(split, QA_SEEDS[0], 0)
            specification = FAMILY_SIGNATURES[FAMILIES[split]]
            self.assertEqual(len(case.public["objects"]), specification["objects"])
            changed = [sum(o["before"][obj] != o["after"][obj] for obj in case.public["objects"])
                       for o in case.oracle["hidden_transitions"]]
            self.assertEqual(max(changed), specification["max_changed_objects"])

    def test_private_solution_is_not_in_comparator_input(self):
        prohibited = {"oracle", "metadata", "seed", "case_index", "case_id", "kind", "split",
                      "family", "expected_status", "witness", "hidden_transitions", "public_sha256"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(prohibited.intersection(value))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        for split in ("development", "validation"):
            for index in range(3):
                public = generate_case(split, QA_SEEDS[0], index).public_input()
                walk(public)
                serialized = json.dumps(public)
                self.assertNotIn("unary_rewrite", serialized)
                self.assertNotIn("guarded_rewrite", serialized)
                self.assertNotIn("insufficient", serialized)

    def test_same_evidence_budget_for_all_task_types(self):
        for split, budget in itertools.product(("development", "validation"), (4, 8, 16)):
            for index in range(9):
                case = generate_case(split, QA_SEEDS[0], index, evidence_budget=budget)
                observations = case.public["observations"]
                self.assertEqual(len(observations), budget)
                pairs = [(json.dumps(o["before"], sort_keys=True), o["action"]) for o in observations]
                self.assertEqual(len(pairs), len(set(pairs)))

    def test_labels_match_exhaustive_independent_evidence_search(self):
        for split, seed, index, budget in itertools.product(
                ("development", "validation"), QA_SEEDS, range(9), (4, 8, 16)):
            with self.subTest(split=split, seed=seed, index=index, budget=budget):
                case = generate_case(split, seed, index, budget)
                plans = independent_supported_plans(case.public)
                expected = "answered" if plans else "insufficient"
                self.assertEqual(case.oracle["expected_status"], expected)
                if plans:
                    self.assertIn(case.oracle["witness"], plans)
                    for plan in plans:
                        self.assertTrue(observed_success(case.public, plan))
                        self.assertTrue(hidden_success(case, plan))

    def test_observations_are_consistent_with_oracle_and_declared_objects(self):
        for split, seed, index in itertools.product(("development", "validation"), QA_SEEDS, range(6)):
            case = generate_case(split, seed, index)
            for o in case.public["observations"]:
                self.assertEqual(set(o["before"]), set(case.public["objects"]))
                self.assertEqual(set(o["after"]), set(case.public["objects"]))
                self.assertIn(o["action"], case.public["actions"])
                matching = [edge for edge in case.oracle["hidden_transitions"]
                            if edge["before"] == o["before"] and edge["action"] == o["action"]]
                self.assertEqual(matching, [o])

    def test_new_names_do_not_repeat_between_qa_worlds(self):
        used = set()
        for split, seed, index in itertools.product(("development", "validation"), QA_SEEDS, range(6)):
            public = generate_case(split, seed, index).public
            names = set(public["objects"]) | set(public["actions"])
            for observation in public["observations"]:
                names.update(observation["before"].values())
                names.update(observation["after"].values())
            self.assertFalse(used & names)
            used.update(names)

    def test_generation_does_not_touch_global_random_state(self):
        before = random.getstate()
        generate_case("validation", QA_SEEDS[1], 7)
        self.assertEqual(before, random.getstate())

    def test_generation_is_reproducible_across_hash_seeds_and_processes(self):
        code = ("import json; from dataclasses import asdict; "
                "from src.research.worlds import generate_case; "
                "print(json.dumps(asdict(generate_case('validation',91307,7)),sort_keys=True))")
        outputs = []
        for hash_seed in ("1", "234", "random"):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed)
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=10, check=True)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_public_input_is_deeply_isolated(self):
        case = generate_case("validation", QA_SEEDS[0], 1)
        original = copy.deepcopy(case)
        first, second = case.public_input(), case.public_input()
        first["observations"][0]["after"].clear()
        first["question"]["goal"].clear()
        first["actions"].append("injected")
        self.assertEqual(case, original)
        self.assertEqual(second, original.public)

    def test_insufficient_information_is_not_hidden_impossibility(self):
        case = generate_case("validation", QA_SEEDS[0], 2)
        self.assertEqual(independent_supported_plans(case.public), [])
        lucky = [list(plan) for plan in itertools.product(case.public["actions"], repeat=2)
                 if hidden_success(case, list(plan))]
        self.assertTrue(lucky, "The task must distinguish unknown from impossible.")
        self.assertTrue(all(not observed_success(case.public, plan) for plan in lucky))
        alternate = copy.deepcopy(case)
        # A second deterministic world agrees with every observation but removes
        # all unobserved effects. The formerly lucky plan now fails.
        for edge in alternate.oracle["hidden_transitions"]:
            if edge not in case.public["observations"]:
                edge["after"] = copy.deepcopy(edge["before"])
        self.assertEqual(alternate.public, case.public)
        self.assertTrue(all(not hidden_success(alternate, plan) for plan in lucky))

    def test_verifier_rejects_conflicting_evidence_and_invalid_plans(self):
        case = generate_case("development", QA_SEEDS[0], 0)
        plan = case.oracle["witness"]
        self.assertTrue(observed_success(case.public, plan))
        corrupt = copy.deepcopy(case.public)
        conflicting = next(copy.deepcopy(o) for o in corrupt["observations"]
                           if o["before"] == corrupt["question"]["initial"] and o["action"] == plan[0])
        conflicting["after"] = copy.deepcopy(conflicting["before"])
        corrupt["observations"].append(conflicting)
        self.assertFalse(observed_success(corrupt, plan))
        for bad in (None, "action", [None], [1], [True], ["unknown"], plan * 3):
            self.assertFalse(observed_success(case.public, bad))
            self.assertFalse(hidden_success(case, bad))

    def test_invalid_generation_arguments_fail_explicitly(self):
        for split in (None, [], "unknown", True):
            with self.assertRaises(ValueError):
                generate_case(split, QA_SEEDS[0], 0)
        for seed in (-1, 2 ** 32, True, 1.0, "7", None):
            with self.assertRaises(ValueError):
                generate_case("validation", seed, 0)
        for index in (-1, 10000, True, 1.0, "7", None):
            with self.assertRaises(ValueError):
                generate_case("validation", QA_SEEDS[0], index)
        for budget in (0, 3, 17, True, 8.0, "8", None):
            with self.assertRaises(ValueError):
                generate_case("validation", QA_SEEDS[0], 0, budget)


class BaselineProperties(unittest.TestCase):
    def test_baselines_preserve_input_and_respect_operation_limit(self):
        for name, baseline in BASELINES.items():
            for index, budget in itertools.product(range(3), (1, 2, 8, 128)):
                with self.subTest(comparator=name, index=index, budget=budget):
                    public = generate_case("validation", QA_SEEDS[1], index).public_input()
                    original = copy.deepcopy(public)
                    result = baseline(public, max_operations=budget)
                    self.assertEqual(public, original)
                    self.assertIn(result["status"], {"answered", "insufficient", "budget_exhausted"})
                    self.assertGreaterEqual(result["operations"], 0)
                    self.assertLessEqual(result["operations"], budget)

    def test_symbolic_search_matches_independent_exhaustive_search(self):
        for split, seed, index in itertools.product(("development", "validation"), QA_SEEDS, range(9)):
            public = generate_case(split, seed, index).public_input()
            plans = independent_supported_plans(public)
            result = symbolic_search(public)
            self.assertEqual(result["status"], "answered" if plans else "insufficient")
            if plans:
                self.assertIn(result["plan"], plans)

    def test_symbolic_search_uses_evidence_instead_of_task_index_or_names(self):
        case = generate_case("validation", QA_SEEDS[0], 1)
        public = case.public_input()
        original = symbolic_search(public)
        self.assertEqual(original["status"], "answered")
        public["observations"].reverse()
        self.assertEqual(symbolic_search(public)["plan"], original["plan"])
        renamed = json.loads(json.dumps(public).replace("obj_", "entidade_").replace("act_", "operador_").replace("val_", "estado_"))
        result = symbolic_search(renamed)
        self.assertEqual(result["status"], original["status"])
        self.assertEqual(result["plan"], [action.replace("act_", "operador_") for action in original["plan"]])
        initial, first = public["question"]["initial"], original["plan"][0]
        public["observations"] = [o for o in public["observations"]
                                  if not (o["before"] == initial and o["action"] == first)]
        self.assertEqual(symbolic_search(public)["status"], "insufficient")

    def test_comparison_references_express_different_capabilities(self):
        public = generate_case("validation", QA_SEEDS[0], 1).public_input()
        self.assertEqual(BASELINES["memory_only"](public)["status"], "insufficient")
        chained = BASELINES["symbolic_search"](public)
        self.assertEqual(chained["status"], "answered")
        self.assertEqual(len(chained["plan"]), 2)
        self.assertTrue(observed_success(public, chained["plan"]))

    def test_invalid_operation_budget_is_rejected_by_all_comparators(self):
        public = generate_case("validation", QA_SEEDS[0], 0).public_input()
        for baseline, budget in itertools.product(BASELINES.values(), (0, -1, 10001, True, 1.0, None)):
            with self.assertRaises(ValueError):
                baseline(public, max_operations=budget)


if __name__ == "__main__":
    unittest.main()
