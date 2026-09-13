"""Declared hand-built references. None is a newly learned reasoning core."""
from collections import Counter, deque

from .worlds import integer, state_key


def answer(status, plan=None, operations=0):
    return {"status": status, "plan": [] if plan is None else list(plan), "operations": operations}


def memory_only(public, max_operations=128):
    """Exact recall of one observed transition, without chaining."""
    integer("max_operations", max_operations, 1, 10000)
    question = public["question"]
    for count, o in enumerate(public["observations"], 1):
        if count > max_operations:
            return answer("budget_exhausted", operations=max_operations)
        if o["before"] == question["initial"] and o["after"] == question["goal"]:
            return answer("answered", [o["action"]], count)
    return answer("insufficient", operations=len(public["observations"]))


def symbolic_search(public, max_operations=128):
    """BFS over observed transitions, with an explicitly programmed composition prior."""
    integer("max_operations", max_operations, 1, 10000)
    q = public["question"]
    queue = deque([(q["initial"], [])])
    visited = {state_key(q["initial"])}
    count = 0
    observations = sorted(public["observations"], key=lambda o: (o["action"], state_key(o["before"])))
    while queue:
        state, plan = queue.popleft()
        if state == q["goal"]:
            return answer("answered", plan, count)
        if len(plan) == q["max_steps"]:
            continue
        for o in observations:
            if count >= max_operations:
                return answer("budget_exhausted", operations=count)
            count += 1
            if o["before"] != state:
                continue
            key = state_key(o["after"])
            if key not in visited:
                visited.add(key)
                queue.append((o["after"], plan + [o["action"]]))
    return answer("insufficient", operations=count)


def empirical_frequency(public, max_operations=128):
    """Fit P(next_state | action) counts, omitting current state on purpose.

    This deliberately simple statistical reference exposes the cost of losing
    context. It is a learned frequency table per episode, not neural training.
    Ties use canonical state/action IDs, a declared arbitrary prior.
    """
    integer("max_operations", max_operations, 1, 10000)
    counts = {}
    states = {}
    operations = 0
    for o in public["observations"]:
        if operations >= max_operations:
            return answer("budget_exhausted", operations=operations)
        operations += 1
        key = state_key(o["after"])
        states[key] = o["after"]
        counts.setdefault(o["action"], Counter())[key] += 1
    predictions = {action: sorted(freq, key=lambda key: (-freq[key], key))[0]
                   for action, freq in counts.items()}
    goal = state_key(public["question"]["goal"])
    # A state-independent modal model predicts the same result on every repeat;
    # a longer plan cannot improve its predicted terminal state.
    for action in sorted(predictions):
        if operations >= max_operations:
            return answer("budget_exhausted", operations=operations)
        operations += 1
        if predictions[action] == goal:
            return answer("answered", [action], operations)
    return answer("insufficient", operations=operations)


BASELINES = {"memory_only": memory_only, "symbolic_search": symbolic_search,
             "empirical_frequency": empirical_frequency}
