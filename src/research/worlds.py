"""Versioned, deterministic finite worlds with a private evaluation oracle.

Only ``WorldCase.public_input()`` may be passed to a comparator. Family names,
seeds, task kinds and solutions are evaluation metadata, never model input.
This is procedural isolation within a trusted Python process, not a sandbox
against malicious comparators able to inspect process memory or source files.
"""
import copy
import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List


GENERATOR_VERSION = "f00-worlds-1"
FAMILIES = {
    "development": "unary_rewrite",
    "validation": "guarded_rewrite",
    "reserved": "coupled_transfer",
}
FAMILY_SIGNATURES = {
    "unary_rewrite": {"objects": 1, "joint_guard": False, "max_changed_objects": 1},
    "guarded_rewrite": {"objects": 2, "joint_guard": True, "max_changed_objects": 1},
    "coupled_transfer": {"objects": 2, "joint_guard": True, "max_changed_objects": 2},
}
TASK_KINDS = ("lookup", "composition", "insufficient")


def integer(name, value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("%s must be an integer in [%s, %s]" % (name, minimum, maximum))
    return value


def state_key(state):
    return json.dumps(state, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(state_key(value).encode("utf-8")).hexdigest()


@dataclass
class WorldCase:
    public: Dict[str, Any]
    oracle: Dict[str, Any]
    metadata: Dict[str, Any]

    def public_input(self):
        return copy.deepcopy(self.public)


def _rng(split, seed, case_index):
    payload = "%s:%s:%s:%s" % (GENERATOR_VERSION, split, seed, case_index)
    return random.Random(int(hashlib.sha256(payload.encode("ascii")).hexdigest(), 16))


def _names(rng, prefix, count):
    return [prefix + "%016x" % n for n in rng.sample(range(1 << 48), count)]


def generate_case(split, seed, case_index, evidence_budget=8):
    """Make one case. Evidence counts are identical across answerability classes.

    Evaluation assumes exact observations of deterministic stationary full
    states. It asks for plans justified by those observations, not recovery of
    arbitrary hidden physical laws. Missing evidence therefore means unknown,
    not a proof of impossibility. Reserved examples must not tune development.
    """
    if not isinstance(split, str) or split not in FAMILIES:
        raise ValueError("split must be development, validation or reserved")
    integer("seed", seed, 0, 2 ** 32 - 1)
    integer("case_index", case_index, 0, 9999)
    integer("evidence_budget", evidence_budget, 4, 16)
    rng = _rng(split, seed, case_index)
    family = FAMILIES[split]
    kind = TASK_KINDS[case_index % len(TASK_KINDS)]
    objects = _names(rng, "obj_", FAMILY_SIGNATURES[family]["objects"])
    actions = _names(rng, "act_", 4)
    symbols = _names(rng, "val_", 6)
    if family == "unary_rewrite":
        states = [{objects[0]: symbol} for symbol in symbols]
    elif family == "guarded_rewrite":
        pairs = [(0, 0), (1, 0), (1, 1), (2, 0), (2, 1), (2, 2)]
        states = [{objects[0]: symbols[x], objects[1]: symbols[y]} for x, y in pairs]
    else:
        total = rng.randint(4, 10)
        pairs = [(0, total), (1, total - 1), (2, total - 2),
                 (3, total - 3), (0, total + 1), (1, total)]
        states = [{objects[0]: x, objects[1]: y} for x, y in pairs]

    # Full deterministic rule table. Unspecified state/action pairs are no-ops.
    rules = {(state_key(s), a): copy.deepcopy(s) for s in states for a in actions}
    second_action = rng.choice(actions[:2])
    decoy_target = rng.choice([3, 5])
    edges = [(0, actions[0], 1), (1, second_action, 2),
             (3, actions[2], 4), (4, actions[3], decoy_target)]
    if family == "coupled_transfer":
        # Each effective transition moves a conserved quantity between objects.
        edges = [(0, actions[0], 1), (1, second_action, 2),
                 (2, actions[2], 3), (4, actions[3], 5)]
    for before, action, after in edges:
        rules[(state_key(states[before]), action)] = copy.deepcopy(states[after])

    def observation(index, action):
        before = states[index]
        return {"before": copy.deepcopy(before), "action": action,
                "after": copy.deepcopy(rules[(state_key(before), action)])}

    evidence = [observation(0, actions[0])]
    if kind != "insufficient":
        evidence.append(observation(1, second_action))
    # Distractors never expose the deliberately missing transition. Keeping
    # their count fixed avoids a trivial answerability label in list length.
    candidates = [observation(i, a) for i in range(6) for a in actions
                  if (i, a) not in {(0, actions[0]), (1, second_action)}]
    rng.shuffle(candidates)
    evidence.extend(candidates[:evidence_budget - len(evidence)])
    rng.shuffle(evidence)
    goal = states[1] if kind == "lookup" else states[2]
    public = {
        "schema_version": "f00-public-1",
        "objects": sorted(objects), "actions": sorted(actions),
        "assumptions": ["fully_observed_state", "deterministic", "stationary",
                        "exact_observations", "only_observed_transitions_justify_a_plan"],
        "observations": evidence,
        "question": {"initial": copy.deepcopy(states[0]), "goal": copy.deepcopy(goal), "max_steps": 2},
    }
    serialized_rules = [{"before": json.loads(before), "action": action, "after": after}
                        for (before, action), after in sorted(rules.items())]
    oracle = {
        "expected_status": "insufficient" if kind == "insufficient" else "answered",
        "witness": [] if kind == "insufficient" else [actions[0]] + ([] if kind == "lookup" else [second_action]),
        "hidden_transitions": serialized_rules,
    }
    metadata = {"generator_version": GENERATOR_VERSION, "split": split, "family": family,
                "kind": kind, "seed": seed, "case_index": case_index,
                "case_id": fingerprint({"split": split, "seed": seed, "index": case_index})[:20],
                "public_sha256": fingerprint(public)}
    return WorldCase(public, oracle, metadata)


def observed_success(public, plan):
    """Independent plan check: every step must exist in the public evidence."""
    if not isinstance(plan, list) or any(not isinstance(a, str) for a in plan):
        return False
    question = public["question"]
    if len(plan) > question["max_steps"]:
        return False
    state = question["initial"]
    for action in plan:
        matches = [o["after"] for o in public["observations"]
                   if o["before"] == state and o["action"] == action]
        if not matches or any(after != matches[0] for after in matches):
            return False
        state = matches[0]
    return state == question["goal"]


def hidden_success(case, plan):
    """Evaluator only: distinguishes lucky unsupported guesses from valid plans."""
    if not isinstance(plan, list) or any(not isinstance(a, str) for a in plan):
        return False
    if len(plan) > case.public["question"]["max_steps"]:
        return False
    state = case.public["question"]["initial"]
    for action in plan:
        matches = [o["after"] for o in case.oracle["hidden_transitions"]
                   if o["before"] == state and o["action"] == action]
        if len(matches) != 1:
            return False
        state = matches[0]
    return state == case.public["question"]["goal"]
