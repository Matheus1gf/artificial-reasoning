"""One auditable learning transaction per conversational turn."""
import re
import uuid

from .domain import claim_text, normalize
from .extraction import EXTRACTION_PROMPT, EXTRACTION_SCHEMA, QUESTION, extract_local, is_correction, validate_neural
from .provider import LanguageModel, ProviderError, Settings
from .reasoner import Reasoner, refers_to_previous, requested_subject, retrieve


class ChatEngine:
    def __init__(self, memory, settings=None, language_model=None):
        self.memory = memory
        self.settings = settings or Settings()
        self.language_model = language_model or LanguageModel(self.settings)
        self.reasoner = Reasoner()

    def reply(self, conversation_id, text, request_id=None, on_token=None):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Escreva uma mensagem.")
        if len(text) > 8000:
            raise ValueError("Use até 8.000 caracteres por mensagem.")
        text = text.strip()
        request_id = request_id or uuid.uuid4().hex
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError("Identificador de envio inválido.")
        with self.memory.transaction():
            self.memory.conversation(conversation_id)
            existing = self.memory.cached_turn(request_id, conversation_id, text)
            if existing:
                return existing
            history = self.memory.messages(conversation_id)
            previous_subject = ""
            for message in reversed(history):
                if message["role"] == "assistant" and message["metadata"].get("focus"):
                    previous_subject = message["metadata"]["focus"]
                    break
            warnings = []
            extracted = extract_local(text, previous_subject)
            neural_available = self.language_model.enabled
            sentences = [s.strip() for s in re.findall(r"[^.!?;\n]+[.!?;]?", text) if s.strip()]
            needs_extraction = any("?" not in s and not QUESTION.match(normalize(s)) for s in sentences)
            if neural_available and needs_extraction:
                try:
                    data = self.language_model.complete(EXTRACTION_PROMPT, {"message": text, "referent": previous_subject}, EXTRACTION_SCHEMA)
                    extracted += validate_neural(data, text, previous_subject)
                except (ProviderError, ValueError) as exc:
                    warnings.append("Extração adicional indisponível; a conversa continua com o modelo. " + str(exc))
            user_id = self.memory.add_message(conversation_id, "user", text)
            learned, invalidated, conflicts = [], [], []
            seen = set()
            for a in extracted:
                key = (a.subject, a.predicate, a.object, a.polarity, a.scope)
                if key in seen:
                    continue
                seen.add(key)
                cid, removed, disputed = self.memory.learn(a, user_id, is_correction(text))
                learned.append(cid)
                invalidated.extend(removed)
                conflicts.extend(disputed)
            # Up to four passes allow multi-step deduction while bounding work and cycles.
            new_deductions = []
            for _ in range(4):
                progress = False
                for proposal in self.reasoner.deduce(self.memory.claims()):
                    c, created = self.memory.propose(proposal)
                    if c["status"] == "disputed":
                        conflicts.extend(other["id"] for other in self.memory.claims()
                                         if other["status"] == "disputed" and
                                         (other["subject"], other["predicate"], other["object"]) ==
                                         (c["subject"], c["predicate"], c["object"]))
                    if created:
                        new_deductions.append(c["id"])
                        progress = True
                if not progress:
                    break
            all_claims = self.memory.claims()
            relevant = retrieve(text, all_claims, previous_subject, conversation_id=conversation_id)
            inferred = []
            for proposal in self.reasoner.explore(text, all_claims, relevant, previous_subject):
                c, created = self.memory.propose(proposal)
                if c["origin"] == "reasoner" and c["status"] in {"hypothesis", "deduced"}:
                    inferred.append(c)
            learned_claims = [self.memory.claim(cid) for cid in dict.fromkeys(learned)]
            for c in relevant:
                if c["status"] == "deduced" and c["id"] not in {i["id"] for i in inferred}:
                    inferred.append(c)
            for cid in new_deductions:
                c = self.memory.claim(cid)
                if c["status"] == "deduced" and c["id"] not in {i["id"] for i in inferred} and any(pid in learned for pid in c["premises"]):
                    inferred.append(c)
            conflict_claims = [c for c in self.memory.claims() if c["status"] == "disputed" and (c["id"] in conflicts or c["id"] in {r["id"] for r in relevant})]
            provider_used = "symbolic"
            if neural_available:
                context = {
                    "memories": [self._context_claim(c) for c in relevant[:8]],
                    "new_learning": [self._context_claim(c) for c in learned_claims[:8]],
                    "inferences": [self._context_claim(c) for c in inferred[:3]],
                    "conflicts": [self._context_claim(c) for c in conflict_claims[:4]],
                    "withdrawn": [{"id": c["id"], "text": claim_text(c), "status": c["status"]}
                                  for c in self.memory.claims(include_inactive=True)
                                  if c["status"] == "retracted"][:10],
                }
                # Failure to extract knowledge does not disable conversation.
                # Failure to generate a reply is surfaced as an error, not replaced
                # by a memory template masquerading as an answer.
                response = self.language_model.chat(text, history, context, on_token=on_token)
                provider_used = self.settings.provider
            else:
                response = self._symbolic_response(text, learned_claims, relevant, inferred, conflict_claims, invalidated, history)
            focus = (learned_claims[0]["subject"] if learned_claims else requested_subject(text) or
                     (relevant[0]["subject"] if relevant else previous_subject if refers_to_previous(text) else ""))
            result = {"conversation_id": conversation_id, "content": response,
                      "learned": learned_claims, "retrieved": relevant, "inferences": inferred,
                      "conflicts": conflict_claims, "invalidated": sorted(set(invalidated)),
                      "focus": focus, "provider": provider_used, "model": self.settings.model if provider_used != "symbolic" else "",
                      "warnings": list(dict.fromkeys(warnings)), "request_id": request_id}
            result["message_id"] = self.memory.add_message(conversation_id, "assistant", response, result)
            result["stats"] = self.memory.stats()
            self.memory.save_turn(request_id, conversation_id, text, result)
            return result

    @staticmethod
    def _context_claim(c):
        return {"id": c["id"], "text": claim_text(c), "status": c["status"],
                "polarity": c["polarity"], "premises": c["premises"],
                "explanation": c["explanation"][:400],
                "source_messages": [s["message_id"] for s in c["sources"][:3]]}

    def _symbolic_response(self, text, learned, relevant, inferred, conflicts, invalidated, history):
        paragraphs = []
        if learned:
            paragraphs.append("Registrei " + ("esta informação" if len(learned) == 1 else "estas informações") + " na memória compartilhada entre suas conversas:\n\n" +
                              "\n".join(f"• {claim_text(c)}. [M{c['id']}]" for c in learned))
            paragraphs.append("Vou tratá-las como " + ("hipóteses informadas" if all(c["status"] == "hypothesis" for c in learned) else "premissas informadas por você") + ", mantendo a origem para futuras revisões.")
        if invalidated:
            paragraphs.append(f"A correção retirou {len(set(invalidated))} conhecimento(s) ou conclusão(ões) que dependiam da versão anterior.")
        if conflicts:
            paragraphs.append("Encontrei afirmações incompatíveis:\n\n" + "\n".join(f"• {claim_text(c)}. [M{c['id']}]" for c in conflicts[:4]) +
                              "\n\nSuspendi seu uso como premissas. Para resolver, escreva ‘Corrigindo:’ seguido da afirmação correta.")
        for c in inferred[:3]:
            label = "Dedução condicional" if c["status"] == "deduced" else "Hipótese por " + {"opposition": "oposição", "analogy": "analogia", "composition": "composição"}.get(c["method"], "exploração")
            sources = " ".join(f"[M{pid}]" for pid in c["premises"])
            paragraphs.append(f"{label}: {claim_text(c)}. [M{c['id']}]\n\n{c['explanation']} {sources}\n\nComo verificar: {c['validation']}")
            if c["method"] == "opposition":
                paragraphs.append("Construir um oposto conceitual não demonstra que ele exista na natureza. Sua existência continua sendo uma questão em aberto nesta memória.")
        if not learned and not inferred:
            usable = [c for c in relevant if c["status"] in {"asserted", "deduced", "hypothesis"}]
            if usable:
                paragraphs.append("Encontrei na memória:\n\n" + "\n".join(
                    f"• {'Hipótese a testar: ' if c['status'] == 'hypothesis' else 'Premissa informada: ' if c['status'] == 'asserted' else 'Dedução condicional: '}{claim_text(c)}. [M{c['id']}]" for c in usable[:5]))
                paragraphs.append("Posso explorar uma oposição, comparar esse conhecimento por analogia ou combinar funções para propor algo novo.")
            elif not conflicts:
                if normalize(text) in {"oi", "ola", "bom dia", "boa noite", "boa tarde"}:
                    paragraphs.append("Olá! Vamos construir conhecimento juntos. Você pode me ensinar uma relação, explorar uma ideia ou retomar um assunto de outra conversa.")
                else:
                    paragraphs.append("Guardei sua mensagem no histórico, mas ainda não encontrei premissas suficientes para responder a esse pedido com o motor local.")
                paragraphs.append("O modo simbólico é uma ferramenta de memória, com interpretação limitada. Ative um modelo de linguagem em Configurações para responder a perguntas gerais e conversar sobre o contexto atual.")
        return "\n\n".join(paragraphs)
