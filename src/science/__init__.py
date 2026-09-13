"""Small, bounded scientific services used by the independent reasoning core."""

import json


def resolve(request):
    """Resolve a JSON domain request without a language model or network access."""
    if not isinstance(request, dict):
        return {"status": "invalid", "sentences": ["O pedido científico deve ser um objeto."],
                "verification": {"passed": False, "checks": []}}
    if not isinstance(request.get("domain"), str):
        return {"status": "invalid", "sentences": ["O domínio científico deve ser um texto."],
                "verification": {"passed": False, "checks": []}, "values": {}}
    from . import physics, quantum, discovery
    service = {"physics": physics, "quantum": quantum, "discovery": discovery}.get(request.get("domain"))
    if service is None:
        return {"status": "unknown", "sentences": ["Domínio científico não implementado."],
                "verification": {"passed": False, "checks": []}}
    try:
        result = service.resolve(request)
        # Finite inputs alone do not guarantee finite intermediate arithmetic.
        # Never let NaN/Infinity or unsupported output escape into an answer package.
        json.dumps(result, allow_nan=False)
        return result
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError) as exc:
        return {"status": "invalid", "sentences": ["Pedido científico inválido: " + str(exc)],
                "verification": {"passed": False, "checks": []}, "values": {}}
