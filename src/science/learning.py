"""A tiny project-trained linear neural layer for explicit physical-prior ablations."""

import random
import math

from .numerics import finite, integer


def features(row, constrained):
    v, a, t = (finite(row[k], k) for k in ("v", "a", "t"))
    # Hard physical boundary: displacement vanishes at t=0. These products are
    # supplied physics priors, not discovered by the neural layer.
    return [v*t, .5*a*t*t] if constrained else [1.0, v, a, t]


def train(rows, constrained, seed=0, epochs=800, learning_rate=.15):
    if not isinstance(constrained, bool):
        raise ValueError("constrained must be boolean")
    integer(seed, 0, 2**32-1, "seed")
    integer(epochs, 1, 10000, "epochs")
    if not isinstance(rows, list) or not 4 <= len(rows) <= 1000:
        raise ValueError("4 to 1000 training rows required")
    learning_rate = finite(learning_rate)
    if not 0 < learning_rate <= 1:
        raise ValueError("learning rate outside (0,1]")
    matrix, targets = [features(r, constrained) for r in rows], [finite(r["target"]) for r in rows]
    scales = [max(1.0, max(abs(r[j]) for r in matrix)) for j in range(len(matrix[0]))]
    matrix = [[value/scale for value, scale in zip(row, scales)] for row in matrix]
    generator = random.Random(seed)
    weights = [generator.uniform(-.1, .1) for _ in scales]
    curve = []
    for epoch in range(epochs):
        errors = [sum(w*x for w, x in zip(weights, row))-y for row, y in zip(matrix, targets)]
        if epoch == 0 or epoch == epochs-1 or epoch % 100 == 0:
            curve.append({"epoch": epoch, "mse": sum(e*e for e in errors)/len(rows)})
        gradients = [2*sum(errors[i]*matrix[i][j] for i in range(len(rows)))/len(rows) for j in range(len(scales))]
        weights = [w-learning_rate*g for w, g in zip(weights, gradients)]
    if any(not math.isfinite(w) for w in weights):
        raise ValueError("training diverged")
    return {"architecture": "single linear neural layer, scalar output, MSE, full-batch gradient descent",
            "constrained": constrained, "weights": weights, "scales": scales, "seed": seed,
            "epochs": epochs, "learning_rate": learning_rate, "learning_curve": curve,
            "training_examples": len(rows), "initialized_by_project": True,
            "prior": "v*t and a*t^2/2 features and zero-displacement boundary supplied" if constrained else "raw v,a,t and intercept"}


def predict(model, row):
    return sum(w*x/s for w, x, s in zip(model["weights"], features(row, model["constrained"]), model["scales"]))
