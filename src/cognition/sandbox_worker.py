"""Trusted worker for a finite numeric DSL, never Python supplied by a user."""
import json
import math
import sys


class BudgetExceeded(Exception):
    pass


def execute(request):
    program = request["program"]
    values = request["inputs"]
    steps, stack = 0, []
    maximum = request["max_steps"]

    def finite(value):
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError("Only finite bounded real numbers are permitted")
        return float(value)

    if not isinstance(values, dict) or len(values) > 256:
        raise ValueError("At most 256 named inputs")
    for name in values:
        if not isinstance(name, str) or not name.isidentifier() or len(name) > 64:
            raise ValueError("Invalid variable name")
        values[name] = finite(values[name])

    def run(instructions, depth=0):
        nonlocal steps
        if not isinstance(instructions, list) or len(instructions) > 1000 or depth > 16:
            raise ValueError("Program shape exceeds bounds")
        for instruction in instructions:
            steps += 1
            if steps > maximum:
                raise BudgetExceeded("Operation budget exhausted")
            if not isinstance(instruction, dict):
                raise ValueError("Instructions must be objects")
            op = instruction.get("op")
            if op == "const" and set(instruction) == {"op", "value"}:
                stack.append(finite(instruction["value"]))
            elif op in ("load", "store") and set(instruction) == {"op", "name"}:
                name = instruction["name"]
                if not isinstance(name, str) or not name.isidentifier() or len(name) > 64:
                    raise ValueError("Invalid variable name")
                if op == "load":
                    stack.append(values[name])
                else:
                    if name not in values and len(values) >= 256:
                        raise ValueError("Variable budget exhausted")
                    values[name] = stack.pop()
            elif op in ("add", "sub", "mul", "div", "pow") and set(instruction) == {"op"}:
                right, left = stack.pop(), stack.pop()
                if op == "add": result = left + right
                elif op == "sub": result = left - right
                elif op == "mul": result = left * right
                elif op == "div": result = left / right
                else:
                    if abs(right) > 10:
                        raise ValueError("Exponent exceeds permitted range")
                    result = left ** right
                stack.append(finite(result))
            elif op == "neg" and set(instruction) == {"op"}:
                stack.append(-stack.pop())
            elif op == "repeat" and set(instruction) == {"op", "count", "body"}:
                count = instruction["count"]
                if type(count) is not int or not 0 <= count <= 100000:
                    raise ValueError("Invalid repeat count")
                for _ in range(count):
                    steps += 1
                    if steps > maximum:
                        raise BudgetExceeded("Operation budget exhausted")
                    run(instruction["body"], depth + 1)
            else:
                raise ValueError("Unrecognized instruction; arbitrary code is prohibited")
            if len(stack) > 1024:
                raise ValueError("Stack budget exhausted")
    try:
        run(program)
        return {"status": "completed", "stack": stack, "values": values, "steps": steps}
    except BudgetExceeded:
        return {"status": "budget_exhausted", "stack": [], "values": {}, "steps": maximum}


def main():
    try:
        raw = sys.stdin.buffer.read(131073)
        if len(raw) > 131072:
            raise ValueError("Input too large")
        request = json.loads(raw)
        # CPU/file/memory constraints supplement the restricted DSL, not a
        # permission to run arbitrary Python inside this process.
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (request["cpu_seconds"], request["cpu_seconds"] + 1))
            resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
            if sys.platform.startswith("linux"):
                maximum = request["memory_mb"] * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
        except (ImportError, ValueError, OSError):
            pass
        result = execute(request)
    except Exception as exc:
        result = {"status": "rejected", "error": type(exc).__name__, "stack": [], "values": {}, "steps": 0}
    sys.stdout.write(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
