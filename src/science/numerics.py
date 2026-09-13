"""Auditable small-matrix operations; no generated Python is executed."""

import math


def finite(value, name="value"):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a finite number")
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return float(value)


def bounded(value, low, high, name):
    value = finite(value, name)
    if not low <= value <= high:
        raise ValueError("{} outside [{}, {}]".format(name, low, high))
    return value


def integer(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError("{} must be an integer in [{}, {}]".format(name, low, high))
    return value


def least_squares(rows, targets):
    """Modified Gram-Schmidt QR with column scaling and a rank check."""
    if not rows or not rows[0] or len(rows) != len(targets):
        raise ValueError("nonempty matching rows and targets required")
    n, p = len(rows), len(rows[0])
    if p > n or any(len(row) != p for row in rows):
        raise ValueError("underdetermined or ragged design matrix")
    matrix = [[finite(x) for x in row] for row in rows]
    y = [finite(x) for x in targets]
    columns = [[row[j] for row in matrix] for j in range(p)]
    scales = [math.sqrt(math.fsum(x*x for x in col)) for col in columns]
    if any(s < 1e-14 for s in scales):
        raise ValueError("unidentifiable parameter: zero column")
    q, r = [], [[0.0]*p for _ in range(p)]
    for j in range(p):
        v = [x/scales[j] for x in columns[j]]
        # Reorthogonalization reduces loss of orthogonality in small polynomial fits.
        for _ in range(2):
            for i in range(j):
                projection = math.fsum(q[i][k]*v[k] for k in range(n))
                r[i][j] += projection
                v = [v[k]-projection*q[i][k] for k in range(n)]
        r[j][j] = math.sqrt(math.fsum(x*x for x in v))
        if r[j][j] < 1e-10:
            raise ValueError("unidentifiable parameters: rank-deficient observations")
        q.append([x/r[j][j] for x in v])
    rhs = [math.fsum(col[k]*y[k] for k in range(n)) for col in q]
    scaled = [0.0]*p
    for j in reversed(range(p)):
        scaled[j] = (rhs[j]-math.fsum(r[j][k]*scaled[k] for k in range(j+1, p)))/r[j][j]
    coefficients = [scaled[j]/scales[j] for j in range(p)]
    residuals = [y[i]-math.fsum(matrix[i][j]*coefficients[j] for j in range(p)) for i in range(n)]
    return {"coefficients": coefficients, "residuals": residuals,
            "rmse": math.sqrt(math.fsum(e*e for e in residuals)/n),
            "rank": p, "observations": n, "degrees_of_freedom": n-p}


def rmse(expected, predicted):
    if len(expected) != len(predicted) or not expected:
        raise ValueError("matching nonempty values required")
    return math.sqrt(math.fsum((finite(a)-finite(b))**2 for a, b in zip(expected, predicted))/len(expected))
