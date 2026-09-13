"""Logical soundness, epistemic distinctions and bounded planning checks."""
import copy
import unittest

from src.cognition.reasoning import (abduce, calculate, causal_evaluate, deduce, induce_affine,
                                     plan, structural_analogy, verify_derivation, verify_plan)


def fact(predicate, arguments, identity="F", polarity=True):
    return {"id": identity, "predicate": predicate, "arguments": arguments, "polarity": polarity}


class DeductionTests(unittest.TestCase):
    def setUp(self):
        self.facts = [fact("parent", ["ana", "bruno"], "F1"), fact("parent", ["bruno", "caio"], "F2")]
        self.rules = [{"id": "R1", "if": [fact("parent", ["?x", "?y"]), fact("parent", ["?y", "?z"])],
                       "then": fact("grandparent", ["?x", "?z"]), "types": {"?x": "person"}}]
        self.types = {"ana": ["person"], "bruno": ["person"], "caio": ["person"]}

    def test_typed_two_premise_deduction_and_independent_replay(self):
        result = deduce(self.facts, self.rules, self.types)
        self.assertEqual(result["status"], "answered")
        self.assertTrue(any(f["predicate"] == "grandparent" and f["arguments"] == ["ana", "caio"] for f in result["facts"]))
        self.assertTrue(verify_derivation(self.facts, self.rules, result["derivation"], self.types))
        self.assertFalse(verify_derivation(self.facts, self.rules, result["derivation"], {"ana": ["rock"]}))

    def test_tampered_binding_premise_or_conclusion_fails_verification(self):
        proof = deduce(self.facts, self.rules, self.types)["derivation"]
        variants = []
        changed = copy.deepcopy(proof); changed[0]["bindings"]["?z"] = "invented"; variants.append(changed)
        changed = copy.deepcopy(proof); changed[0]["premise_ids"][0] = "missing"; variants.append(changed)
        changed = copy.deepcopy(proof); changed[0]["conclusion"]["polarity"] = False; variants.append(changed)
        changed = copy.deepcopy(proof); changed[0]["conclusion"]["arguments"] = ["ana", "invented"]; variants.append(changed)
        for variant in variants:
            self.assertFalse(verify_derivation(self.facts, self.rules, variant, self.types))

    def test_contradictions_are_rejected_by_search_and_verifier(self):
        positive = fact("p", ["a"], "F1")
        negative = fact("p", ["a"], "F2", False)
        rule = {"id": "R", "if": [fact("p", ["?x"])], "then": fact("q", ["?x"])}
        proof = deduce([positive], [rule])["derivation"]
        self.assertEqual(deduce([positive, negative], [rule])["status"], "contradictory")
        self.assertFalse(verify_derivation([positive, negative], [rule], proof))
        opposed_conclusion = fact("q", ["a"], "F3", False)
        self.assertFalse(verify_derivation([positive, opposed_conclusion], [rule], proof))

    def test_unbound_variables_and_free_variables_in_facts_are_rejected(self):
        bad_rule = {"if": [fact("p", ["?x"])], "then": fact("q", ["?unbound"])}
        with self.assertRaises(ValueError):
            deduce([fact("p", ["a"])], [bad_rule])
        with self.assertRaises(ValueError):
            deduce([fact("p", ["?free"])], [])

    def test_missing_type_blocks_inference_and_operation_limit_is_honest(self):
        self.assertEqual(deduce(self.facts, self.rules, {})["derivation"], [])
        limited = deduce(self.facts, self.rules, self.types, max_operations=1)
        self.assertEqual(limited["status"], "budget_exhausted")
        self.assertLessEqual(limited["operations"], 1)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.initial = {"color": "blue", "ready": False}
        self.goal = {"color": "red"}
        self.actions = [
            {"name": "prepare", "preconditions": {"color": "blue"}, "effects": {"ready": True}, "cost": 1},
            {"name": "change", "preconditions": {"color": "blue", "ready": True}, "effects": {"color": "red"}, "cost": 1},
            {"name": "expensive", "preconditions": {"color": "blue"}, "effects": {"color": "red"}, "cost": 7},
            {"name": "cycle", "preconditions": {"color": "red"}, "effects": {"color": "blue"}, "cost": 0},
        ]

    def test_planner_finds_low_cost_plan_and_verifier_replays_actual_preconditions(self):
        result = plan(self.initial, self.goal, self.actions)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["plan"], ["prepare", "change"])
        self.assertEqual(result["cost"], 2)
        self.assertTrue(verify_plan(self.initial, self.goal, self.actions, result["plan"]))
        self.assertFalse(verify_plan(self.initial, self.goal, self.actions, ["change"]))
        self.assertFalse(verify_plan(self.initial, self.goal, self.actions, ["unknown"]))

    def test_scalar_types_are_consistent_between_planner_and_verifier(self):
        actions = [{"name": "set", "preconditions": {"x": 1}, "effects": {"x": True}}]
        result = plan({"x": 1}, {"x": True}, actions)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["plan"], ["set"])
        self.assertTrue(verify_plan({"x": 1}, {"x": True}, actions, result["plan"]))

    def test_horizon_unknown_and_budget_exhaustion_are_distinct(self):
        actions = self.actions[:2]
        self.assertEqual(plan(self.initial, self.goal, actions, max_steps=1)["status"], "unknown")
        limited = plan(self.initial, self.goal, actions, max_operations=1)
        self.assertEqual(limited["status"], "budget_exhausted")
        self.assertLessEqual(limited["operations"], 1)
        states_limited = plan(self.initial, self.goal, actions, max_states=1)
        self.assertEqual(states_limited["status"], "budget_exhausted")

    def test_negative_cost_and_unknown_variables_are_rejected(self):
        with self.assertRaises(ValueError):
            plan({"x": 0}, {"x": 1}, [{"name": "bad", "effects": {"x": 1}, "cost": -1}])
        with self.assertRaises(ValueError):
            plan({"x": 0}, {"x": 1}, [{"name": "bad", "effects": {"y": 1}}])


class InductionAbductionAnalogyTests(unittest.TestCase):
    def test_induction_preserves_multiple_models_and_learns_after_discriminating_example(self):
        initial = induce_affine([{"x": 0, "y": 1}], query=2)
        self.assertEqual(initial["status"], "ambiguous")
        self.assertGreater(len(initial["candidates"]), 1)
        query = initial["next_query"]
        learned = induce_affine([{"x": 0, "y": 1}, {"x": query, "y": 2 * query + 1}], query=3)
        self.assertEqual(learned["status"], "answered")
        self.assertEqual(learned["predictions"], [7])
        self.assertEqual((learned["candidates"][0]["a"], learned["candidates"][0]["b"]), (2, 1))

    def test_counterexamples_remove_candidates_and_incomplete_search_never_claims_unique_rule(self):
        result = induce_affine([{"x": 0, "y": 1}], query=2, counterexamples=[{"x": 1, "not_y": 2}])
        self.assertTrue(all(not (m["a"] == 1 and m["b"] == 1) for m in result["candidates"]))
        self.assertEqual(induce_affine([{"x": 0, "y": 1}], query=2, max_operations=1)["status"], "budget_exhausted")
        self.assertEqual(induce_affine([{"x": 0, "y": 100}], query=2)["status"], "unknown")

    def test_abduction_lists_competing_causes_and_does_not_promote_them_to_facts(self):
        rules = [{"id": "R-rain", "if": [fact("rain", ["?place"])], "then": fact("wet", ["?place"])},
                 {"id": "R-sprinkler", "if": [fact("sprinkler", ["?place"])], "then": fact("wet", ["?place"])}]
        result = abduce([], rules, fact("wet", ["garden"]))
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["explanations"]), 2)
        self.assertTrue(all(c["status"] == "hypothesis" and c["test"] for c in result["explanations"]))
        narrowed = abduce([fact("rain", ["garden"], polarity=False)], rules, fact("wet", ["garden"]))
        self.assertEqual([c["rule_id"] for c in narrowed["explanations"]], ["R-sprinkler"])

    def test_analogy_requires_structure_and_respects_negative_target_evidence(self):
        source = [fact("feeds", ["a", "b"], "S1"), fact("controls", ["a", "b"], "S2"), fact("powers", ["a", "b"], "S3")]
        target = [fact("feeds", ["x", "y"], "T1"), fact("controls", ["x", "y"], "T2")]
        result = structural_analogy(source, target, ["a", "b"], ["x", "y"], mapping={"a": "x", "b": "y"})
        self.assertEqual(result["status"], "answered")
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["conclusion"]["arguments"], ["x", "y"])
        self.assertEqual(result["proposals"][0]["status"], "hypothesis")
        self.assertTrue(result["proposals"][0]["requires_test"])
        blocked = structural_analogy(source, target + [fact("powers", ["x", "y"], "T3", False)],
                                     ["a", "b"], ["x", "y"], mapping={"a": "x", "b": "y"})
        self.assertEqual(blocked["proposals"], [])
        superficial = structural_analogy(source, target[:1], ["a", "b"], ["x", "y"])
        self.assertEqual(superficial["proposals"], [])


class CausalAndCalculationTests(unittest.TestCase):
    def setUp(self):
        self.model = {"rain": {"op": "input"}, "sprinkler": {"op": "input"},
                      "wet": {"op": "or", "args": ["rain", "sprinkler"]}}

    def test_intervention_replaces_mechanism_and_preserves_exogenous_inputs(self):
        result = causal_evaluate(self.model, {"rain": 1, "sprinkler": 0}, intervention={"wet": 0}, factual={"wet": 1})
        self.assertEqual(result["factual"]["wet"], 1)
        self.assertEqual(result["intervened"]["wet"], 0)
        self.assertEqual(result["intervened"]["rain"], 1)
        self.assertTrue(result["identifiable"])

    def test_missing_exogenous_values_inconsistent_facts_and_cycles_do_not_get_answers(self):
        self.assertEqual(causal_evaluate(self.model, {"rain": 1})["status"], "unknown")
        self.assertEqual(causal_evaluate(self.model, {"rain": 1, "sprinkler": 0}, factual={"wet": 0})["status"], "contradictory")
        cyclic = {"a": {"op": "copy", "args": ["b"]}, "b": {"op": "copy", "args": ["a"]}}
        with self.assertRaises(ValueError):
            causal_evaluate(cyclic, {})

    def test_arithmetic_is_dimension_checked_and_rejects_code_execution(self):
        variables = {"v": {"value": 3, "dimensions": [1, -1, 0]}, "t": {"value": 2, "dimensions": [0, 1, 0]},
                     "x": {"value": 1, "dimensions": [1, 0, 0]}}
        result = calculate("x + v*t", variables)
        self.assertEqual(result["value"], 7)
        self.assertEqual(result["dimensions"], [1, 0, 0])
        for expression in ("x+t", "1/0", "True+1", "2**10000", "__import__('os').getcwd()", "[x for x in range(100)]"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                calculate(expression, variables)


if __name__ == "__main__":
    unittest.main()
