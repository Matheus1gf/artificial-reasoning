"""Dense pure-state simulation and bounded inference on one-qubit systems.

No quantum hardware, quantum-brain assumptions, or claimed computational advantage.
"""

import math
import random
import time

from .numerics import bounded, finite, integer

H = [[1/math.sqrt(2), 1/math.sqrt(2)], [1/math.sqrt(2), -1/math.sqrt(2)]]
X = [[0, 1], [1, 0]]
Z = [[1, 0], [0, -1]]


def complex_number(value):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return complex(finite(value[0]), finite(value[1]))
    if isinstance(value, complex):
        return complex(finite(value.real), finite(value.imag))
    return complex(finite(value))


def state_vector(state):
    if not isinstance(state, (tuple, list)) or not 2 <= len(state) <= 256 or len(state) & (len(state)-1):
        raise ValueError("state must have 2^n amplitudes for 1 to 8 qubits")
    vector = [complex_number(x) for x in state]
    if abs(sum(abs(x)**2 for x in vector)-1) > 1e-9:
        raise ValueError("state must be normalized; invalid input is not silently normalized")
    return vector


def operator_matrix(matrix, size):
    if not isinstance(matrix, (tuple, list)) or len(matrix) != size or any(not isinstance(row, (tuple, list)) or len(row) != size for row in matrix):
        raise ValueError("operator shape must match state")
    return [[complex_number(x) for x in row] for row in matrix]


def unitary_error(matrix):
    n = len(matrix)
    return max(abs(sum(matrix[k][i].conjugate()*matrix[k][j] for k in range(n))-(1 if i == j else 0))
               for i in range(n) for j in range(n))


def apply_unitary(state, matrix):
    vector = state_vector(state)
    # Cubic verification is intentionally bounded more tightly than the vector size.
    if len(vector) > 32:
        raise ValueError("general dense operators limited to 5 qubits; sparse cost benchmark supports 8")
    matrix = operator_matrix(matrix, len(vector))
    error = unitary_error(matrix)
    if error > 1e-9:
        raise ValueError("operator is not unitary")
    result = [sum(row[j]*vector[j] for j in range(len(vector))) for row in matrix]
    state_vector(result)
    return result


def born_probabilities(state):
    return [abs(z)**2 for z in state_vector(state)]


def expectation(state, observable):
    vector = state_vector(state)
    matrix = operator_matrix(observable, len(vector))
    if max(abs(matrix[i][j]-matrix[j][i].conjugate()) for i in range(len(vector)) for j in range(len(vector))) > 1e-9:
        raise ValueError("observable must be Hermitian")
    result = sum(vector[i].conjugate()*matrix[i][j]*vector[j] for i in range(len(vector)) for j in range(len(vector)))
    return result.real


def rotation_x(angle):
    angle = bounded(angle, -1000, 1000, "angle")
    c, s = math.cos(angle/2), -1j*math.sin(angle/2)
    return [[c, s], [s, c]]


def evolve(state, omega, duration):
    omega = bounded(omega, 0, 20, "omega")
    duration = bounded(duration, 0, 10, "duration")
    if len(state) != 2:
        raise ValueError("Rx evolution supports one qubit only")
    return apply_unitary(state, rotation_x(omega*duration))


def measure(state, shots=1000, seed=0):
    probabilities = born_probabilities(state)
    integer(shots, 1, 100000, "shots")
    integer(seed, 0, 2**32-1, "seed")
    generator, counts = random.Random(seed), [0]*len(probabilities)
    for _ in range(shots):
        sample, cumulative = generator.random(), 0.0
        for i, probability in enumerate(probabilities):
            cumulative += probability
            if sample < cumulative or i == len(probabilities)-1:
                counts[i] += 1
                break
    return {"probabilities": probabilities, "counts": counts, "shots": shots, "seed": seed,
            "preparation": "independent identical pure-state preparations per shot",
            "post_measurement_rule": "computational basis state at sampled outcome",
            "probability_sum_error": abs(sum(probabilities)-1)}


def fit_frequency(observations, candidates=None):
    """Maximum-likelihood candidate frequencies; only observed time/counts enter."""
    if not isinstance(observations, list) or not 1 <= len(observations) <= 1000:
        raise ValueError("1 to 1000 observed count records required")
    candidates = [i/50 for i in range(101)] if candidates is None else candidates
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= 1001:
        raise ValueError("2 to 1001 candidate frequencies required")
    candidates = [bounded(c, 0, 20, "candidate omega") for c in candidates]
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate frequencies must be distinct")
    points = []
    for obs in observations:
        t = bounded(obs["t"], 0, 10, "measurement time")
        shots = integer(obs["shots"], 1, 100000, "shots")
        zeros = integer(obs["zeros"], 0, shots, "zeros")
        points.append((t, shots, zeros))
    scored = []
    for omega in candidates:
        loss = 0.0
        for t, shots, zeros in points:
            # Known model class (Rx) is declared; only omega is learned.
            p = min(1-1e-15, max(1e-15, math.cos(omega*t/2)**2))
            loss -= zeros*math.log(p)+(shots-zeros)*math.log1p(-p)
        scored.append((loss, omega))
    scored.sort()
    best = scored[0][0]
    weights = [math.exp(-(loss-best)) for loss, _ in scored]
    total = sum(weights)
    plausible = [omega for loss, omega in scored if loss-best <= 2]
    return {"omega": scored[0][1], "negative_log_likelihood": best,
            "ranked_candidates": [{"omega": omega, "nll": loss, "normalized_likelihood": weight/total}
                                  for (loss, omega), weight in zip(scored, weights)],
            "plausible_candidates": plausible, "ambiguous": len(plausible) > 1,
            "model_class": "closed one-qubit Rx with initial |0>, ideal Z measurement",
            "units": {"omega": "rad/s", "t": "s"},
            "uncertainty": "normalized likelihood over supplied finite candidates, not calibrated scientific confidence"}


def choose_measurement(candidates, times):
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= 1001:
        raise ValueError("2 to 1001 frequency candidates required")
    if not isinstance(times, list) or not 1 <= len(times) <= 1000:
        raise ValueError("1 to 1000 available measurement times required")
    candidates = [bounded(w, 0, 20, "omega") for w in candidates]
    times = [bounded(t, 0, 10, "time") for t in times]
    records = []
    for t in times:
        ps = [math.cos(w*t/2)**2 for w in candidates]
        mean = sum(ps)/len(ps)
        variance = sum((p-mean)**2 for p in ps)/len(ps)
        records.append({"t": t, "prediction_variance": variance, "probabilities": ps})
    selected = max(records, key=lambda r: r["prediction_variance"])
    return {"selected": selected, "alternatives": records,
            "method": "maximize candidate prediction variance under uniform candidate weight",
            "informative": selected["prediction_variance"] > 1e-12}


def sequential_probability(theta, phi, order, first=0, second=0):
    """Real-plane projective quantum model: initial theta, basis A=0, B=phi."""
    theta, phi = finite(theta), finite(phi)
    if order not in ("AB", "BA") or first not in (0, 1) or second not in (0, 1):
        raise ValueError("order AB/BA and binary outcomes required")
    a, b = (0.0, phi) if order == "AB" else (phi, 0.0)
    psi = [math.cos(theta), math.sin(theta)]
    first_basis = [math.cos(a+first*math.pi/2), math.sin(a+first*math.pi/2)]
    second_basis = [math.cos(b+second*math.pi/2), math.sin(b+second*math.pi/2)]
    initial = sum(x*y for x, y in zip(psi, first_basis))**2
    transition = sum(x*y for x, y in zip(first_basis, second_basis))**2
    return initial*transition


def classical_context_probability(theta, phi, order, first=0, second=0):
    """Two-parameter context-conditioned Markov model, algebraically equivalent.

    It samples classical conditional probabilities and has no complex state.
    Equivalence is an intentionally strong classical null, not a novel theorem.
    """
    theta, phi = finite(theta), finite(phi)
    if order not in ("AB", "BA") or first not in (0, 1) or second not in (0, 1):
        raise ValueError("order AB/BA and binary outcomes required")
    first_context = 0 if order == "AB" else phi
    p_first_zero = math.cos(theta-first_context)**2
    p_first = p_first_zero if first == 0 else 1-p_first_zero
    p_same = math.cos(phi)**2
    return p_first*(p_same if first == second else 1-p_same)


def contextual_fit(observations, model="quantum", grid_size=21):
    integer(grid_size, 3, 101, "grid_size")
    if model not in ("quantum", "classical_context"):
        raise ValueError("unknown context model")
    if not isinstance(observations, list) or not 1 <= len(observations) <= 1000:
        raise ValueError("1 to 1000 observations required")
    if grid_size*grid_size*len(observations) > 200000:
        raise ValueError("context fitting exceeds the bounded candidate-record budget")
    probability = sequential_probability if model == "quantum" else classical_context_probability
    rows = []
    for row in observations:
        order = row["order"]
        if order not in ("AB", "BA"):
            raise ValueError("invalid context order")
        counts = row["counts"]
        if not isinstance(counts, list) or len(counts) != 4:
            raise ValueError("four joint-outcome counts required")
        counts = [integer(c, 0, 100000, "count") for c in counts]
        if sum(counts) == 0:
            raise ValueError("positive count sum required")
        rows.append((order, counts))
    best = None
    for i in range(grid_size):
        theta = math.pi*i/(2*(grid_size-1))
        for j in range(grid_size):
            phi = math.pi*j/(2*(grid_size-1))
            loss = 0.0
            for order, counts in rows:
                for k, count in enumerate(counts):
                    p = probability(theta, phi, order, k//2, k % 2)
                    loss -= count*math.log(max(1e-15, p))
            candidate = (loss, theta, phi)
            if best is None or candidate < best:
                best = candidate
    return {"model": model, "nll": best[0], "theta": best[1], "phi": best[2],
            "free_parameters": 2, "grid_evaluations": grid_size**2,
            "data_kind": "caller supplied; simulator experiment is synthetic, not human evidence"}


def state_cost(qubits, repeats=10):
    integer(qubits, 1, 8, "qubits")
    integer(repeats, 1, 1000, "repeats")
    size = 2**qubits
    vector = [0j]*size
    vector[0] = 1+0j
    start = time.perf_counter()
    for _ in range(repeats):
        # Diagonal phase gate is O(2^n); no dense matrix is allocated.
        vector = [amplitude*(1j if index & 1 else 1) for index, amplitude in enumerate(vector)]
    elapsed = time.perf_counter()-start
    return {"qubits": qubits, "amplitudes": size, "complex128_payload_bytes": 16*size,
            "python_storage_note": "Python objects/list overhead exceed the ideal payload estimate",
            "elapsed_seconds": elapsed, "repeats": repeats,
            "normalization_error": abs(sum(abs(z)**2 for z in vector)-1)}


def resolve(request):
    parameters = request.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    operation = request.get("operation")
    status, parameter_identified = "answered", None
    if operation == "evolve":
        vector = evolve(**parameters)
        result = {"state": [[z.real, z.imag] for z in vector], "probabilities": born_probabilities(vector),
                  "norm_error": abs(sum(abs(z)**2 for z in vector)-1)}
        sentence = "A evolução unitária retornou probabilidades {} na base de medição.".format(result["probabilities"])
    elif operation == "measure":
        result = measure(**parameters)
        sentence = "A simulação de medições retornou as contagens {} em {} preparações independentes.".format(result["counts"], result["shots"])
    elif operation == "fit":
        result = fit_frequency(**parameters)
        parameter_identified = not result["ambiguous"]
        if result["ambiguous"]:
            status = "unknown"
        sentence = "A frequência candidata com maior verossimilhança é {:.8g} rad/s; {} candidatos permanecem plausíveis.".format(result["omega"], len(result["plausible_candidates"]))
    elif operation == "measurement_choice":
        result = choose_measurement(**parameters)
        if not result["informative"]:
            status = "unknown"
        sentence = "O teste com maior dispersão entre previsões candidatas ocorre em t={:.8g} s.".format(result["selected"]["t"])
    elif operation == "cost":
        result = state_cost(**parameters)
        sentence = "O vetor de estado usa {} amplitudes complexas para {} qubits.".format(result["amplitudes"], result["qubits"])
    elif operation == "contextual_study":
        if parameters:
            raise ValueError("registered human-context study does not accept runtime overrides")
        from . import human_context
        result = human_context.evaluate()
        sentence = "A reanálise de duas experiências humanas publicadas comparou modelos contextual clássico e quântico com dois parâmetros e o mesmo orçamento; ajuste não prova superioridade de raciocínio."
    else:
        raise ValueError("unknown quantum operation")
    return {"status": status, "values": result, "sentences": [sentence], "conclusions": [sentence],
            "units": result.get("units", {}),
            "verification": {"passed": True, "parameter_identified": parameter_identified,
                             "checks": [operation, "finite bounded input", "declared pure-state model"]},
            "premises": ([result["source_url"], "Reanálise de estatísticas humanas agregadas publicadas."] if operation == "contextual_study"
                         else ["Simulação clássica de sistemas quânticos pequenos; nenhuma execução em hardware quântico."]),
            "limitations": ["Não demonstra cognição humana ou vantagem em invenção.",
                            "Inferência aprende parâmetros dentro de uma classe fornecida, não a mecânica quântica inteira."]}
