"""Independent QA of scoped memory, provenance, revision and recovery."""
import copy
import subprocess
import sys
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.cognition.store import ExperienceStore, SCHEMA_VERSION


def create_v1(path):
    db = sqlite3.connect(str(path))
    db.executescript("""
        CREATE TABLE store_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT INTO store_meta VALUES('schema_version','1');
        CREATE TABLE records(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,
          owner_id TEXT NOT NULL,kind TEXT NOT NULL,scope TEXT NOT NULL,status TEXT NOT NULL,
          evidence TEXT NOT NULL,payload TEXT NOT NULL,source_ids TEXT NOT NULL,created_at TEXT NOT NULL);
    """)
    db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?)", (
        "E-original", "old-conversation", "local", "assertion", "conversation", "asserted", "user",
        json.dumps({"text": "Dado anterior que deve ser preservado."}), "[]", "2026-09-08T00:00:00Z"))
    db.commit()
    db.close()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ar-store-qa-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.store = ExperienceStore(self.directory / "store.sqlite3")
        self.addCleanup(self.store.close)

    def test_goal_unification_preserves_shared_variables_and_predicate_aliases(self):
        from src.cognition.store import structural_match
        matching = self.store.record("c1", "relation", {"predicate":"absorve","arguments":["A","A"]}, [])
        other = self.store.record("c1", "relation", {"predicate":"absorve","arguments":["A","B"]}, [])
        found = self.store.retrieve("c1", {"goal":{"predicate":"absorver","arguments":["?x","?x"]}})
        self.assertEqual([item["id"] for item in found], [matching])
        self.assertFalse(structural_match({"arguments":["?x","?x"]}, {"arguments":[1,True]}))
        self.assertFalse(structural_match({"arguments":[True]}, {"arguments":[1]}))

    def test_legacy_import_is_idempotent_preserves_hypotheses_and_source_withdrawal(self):
        claims=[{"id":1,"subject":"A","predicate":"emite","object":"luz","status":"asserted","origin":"user"},
                {"id":2,"subject":"B","predicate":"emite","object":"luz","status":"hypothesis","origin":"reasoner","premises":[1]}]
        snapshot=copy.deepcopy(claims)
        ids=self.store.import_claims(claims)
        self.assertEqual(self.store.import_claims(claims),ids)
        self.assertEqual(claims,snapshot)
        self.assertEqual(self.store.get(ids[1])["evidence"],"generated")
        self.assertEqual(self.store.get(ids[1])["status"],"hypothesis")
        self.assertEqual({item["id"] for item in self.store.retrieve("new",{})},set(ids))
        self.store.invalidate_sources(["M1"])
        self.assertEqual(self.store.retrieve("new",{}),[])

    def test_administration_cli_backup_export_restore_forget_and_nonoverwrite(self):
        rid=self.assertion("CLI record")
        root=Path(__file__).resolve().parents[2]
        base=[sys.executable,str(root/"scripts/manage_cognition.py"),"--database",self.store.path]
        backup=self.directory/"cli-backup.db"; exported=self.directory/"cli-export.json"; restored=self.directory/"restored.db"
        for action,path in (("backup",backup),("export",exported)):
            process=subprocess.run(base+[action,str(path)],capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            json.loads(process.stdout)
            old=path.read_bytes()
            again=subprocess.run(base+[action,str(path)],capture_output=True,text=True)
            self.assertNotEqual(again.returncode,0)
            self.assertEqual(path.read_bytes(),old)
        output=subprocess.run([sys.executable,str(root/"scripts/manage_cognition.py"),"--database",str(backup),"restore",str(restored)],capture_output=True,text=True)
        self.assertEqual(output.returncode,0,output.stderr)
        check=ExperienceStore(restored)
        try: self.assertEqual(check.get(rid)["payload"],{"text":"CLI record"})
        finally: check.close()
        erased=subprocess.run(base+["forget",rid],capture_output=True,text=True)
        self.assertEqual(erased.returncode,0,erased.stderr)
        self.assertEqual(self.store.export()["records"],[])

    def assertion(self, text="Observação fornecida.", conversation="c1", **kwargs):
        return self.store.record(conversation, "assertion", {"text": text}, [], **kwargs)

    def verified_experiment(self, label="training", **kwargs):
        return self.store.record("c1", "experiment", {"name": label, "observations": [{"x": 1, "y": 2}]},
                                 ["dataset:qa:" + label], status="verified", evidence="experiment",
                                 uncertainties={"derivation": "verified"}, **kwargs)

    def validation(self, label="validation", passed=True):
        return self.store.record("c1", "test_result", {
            "split": "validation", "metrics": {"error": 0.01, "passed": passed, "retention_passed": True}
        }, ["dataset:qa:" + label], status="verified", evidence="experiment",
            uncertainties={"derivation": "verified"})

    def register(self, training, validation, weights=1, **kwargs):
        return self.store.register_model("qa-model", {"architecture": "linear", "weights": [weights]}, [training],
                                         {"passed": True, "retention_passed": True, "validation_id": validation}, **kwargs)

    def test_record_preserves_provenance_and_separate_uncertainty_dimensions(self):
        rid = self.store.record("c1", "relation", {"predicate": "transfers", "arguments": ["A", "B", 3]},
                                ["source:qa:1"], valid_time="2026-09-08", logical_key="transfer:A:B",
                                uncertainties={"extraction": .8, "source": .4, "event": .2, "derivation": "conditional"})
        record = self.store.get(rid, conversation_id="c1")
        self.assertEqual(record["source_ids"], ["source:qa:1"])
        self.assertEqual(record["payload"]["arguments"], ["A", "B", 3])
        self.assertEqual(record["uncertainties"], {"extraction": .8, "source": .4, "event": .2, "derivation": "conditional"})
        self.assertEqual(record["version"], 1)
        self.assertTrue(record["created_at"])

    def test_scope_isolation_for_conversation_user_and_laboratory(self):
        private = self.assertion("privado", owner_id="alice")
        shared_user = self.assertion("usuário", scope="user", owner_id="alice")
        laboratory = self.assertion("laboratório", scope="laboratory", owner_id="alice")
        self.assertEqual({r["id"] for r in self.store.retrieve("c2", {}, owner_id="alice")}, {shared_user, laboratory})
        self.assertEqual({r["id"] for r in self.store.retrieve("c1", {}, owner_id="bob")}, {laboratory})
        with self.assertRaises(ValueError):
            self.store.get(private, owner_id="bob")
        with self.assertRaises(ValueError):
            self.store.get(private, owner_id="alice", conversation_id="c2")
        for method in (self.store.retract, self.store.forget):
            with self.assertRaises(ValueError):
                method(laboratory, owner_id="bob")
        with self.assertRaises(ValueError):
            self.store.revise(laboratory, {"text": "inválido"}, owner_id="bob")

    def test_external_owner_or_conversation_cannot_supply_private_premise(self):
        private = self.assertion(owner_id="alice")
        for owner, conversation in (("bob", "c1"), ("alice", "c2")):
            with self.assertRaises(ValueError):
                self.store.record(conversation, "hypothesis", {"text": "conclusão"}, [private],
                                  owner_id=owner, evidence="generated", status="hypothesis")

    def test_revision_invalidates_transitive_models_and_plans_but_preserves_other_context(self):
        premise = self.assertion("versão antiga")
        rule = self.store.record("c1", "rule", {"conditions": [{"source": premise}], "effects": [{"value": 2}]}, [premise])
        plan = self.store.record("c1", "procedure", {"plan": ["action"]}, [rule])
        unrelated = self.assertion("independente", conversation="c2")
        revised = self.store.revise(premise, {"text": "versão corrigida"})
        for rid in (premise, rule, plan):
            self.assertEqual(self.store.get(rid)["status"], "retracted")
        record = self.store.get(revised)
        self.assertEqual(record["parent_id"], premise)
        self.assertEqual(record["version"], 2)
        self.assertEqual(self.store.get(unrelated)["status"], "asserted")

    def test_different_times_do_not_conflict_and_same_time_conflicts_invalidate_dependents(self):
        first = self.store.record("c1", "attribute", {"entity": "A", "name": "x", "value": 1}, [],
                                  logical_key="A:x", valid_time="t0")
        later = self.store.record("c1", "attribute", {"entity": "A", "name": "x", "value": 2}, [],
                                  logical_key="A:x", valid_time="t1")
        self.assertEqual(self.store.get(first)["status"], "asserted")
        self.assertEqual(self.store.get(later)["status"], "asserted")
        dependent = self.store.record("c1", "procedure", {"plan": []}, [first])
        conflict = self.store.record("c1", "attribute", {"entity": "A", "name": "x", "value": 9}, [],
                                     logical_key="A:x", valid_time="t0")
        self.assertEqual(self.store.get(first)["status"], "disputed")
        self.assertEqual(self.store.get(conflict)["status"], "disputed")
        self.assertEqual(self.store.get(dependent)["status"], "retracted")
        self.assertEqual(self.store.get(later)["status"], "asserted")

    def test_withdrawn_and_hypothetical_premises_cannot_certify_new_knowledge(self):
        premise = self.assertion()
        self.store.retract(premise)
        with self.assertRaises(ValueError):
            self.store.record("c1", "procedure", {"plan": []}, [premise])
        hypothetical = self.store.record("c1", "hypothesis", {"text": "talvez"}, [], status="hypothesis", evidence="generated")
        with self.assertRaises(ValueError):
            self.store.record("c1", "procedure", {"plan": []}, [hypothetical], status="verified", evidence="deduction")

    def test_generated_text_and_user_assertions_cannot_self_verify(self):
        for evidence in ("generated", "user", "imported"):
            with self.assertRaises(ValueError):
                self.store.record("c1", "assertion", {"text": "verdade"}, [], status="verified", evidence=evidence)
        with self.assertRaises(ValueError):
            self.store.record("c1", "assertion", {"text": "gerado"}, [], status="asserted", evidence="generated")

    def test_invalid_typed_payloads_are_rejected(self):
        invalid = [("relation", {"predicate": "rel", "arguments": "not a list"}),
                   ("state", {"values": "not a mapping"}),
                   ("rule", {"conditions": None, "effects": []}),
                   ("action", {"preconditions": [], "effects": "not a list"}),
                   ("equation", {"expression": 123, "variables": "not a collection"})]
        for kind, payload in invalid:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.store.record("c1", kind, payload, [])

    def test_uncertainty_nonfinite_and_unknown_dimensions_rejected(self):
        for data in ({"confidence": .99}, {"source": float("nan")}, {"event": 1.1},
                     {"extraction": True}, {"derivation": "certain"}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.assertion(uncertainties=data)

    def test_idempotency_prevents_duplicate_experiences_and_rejects_changed_payload(self):
        first = self.assertion(dedupe_key="qa-once")
        self.assertEqual(first, self.assertion(dedupe_key="qa-once"))
        self.assertEqual(len(self.store.export()["records"]), 1)
        with self.assertRaises(ValueError):
            self.assertion("alterado", dedupe_key="qa-once")

    def test_outer_transaction_rolls_back_nested_record_on_failure(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.assertion("deve desaparecer")
                raise RuntimeError("failed turn")
        self.assertEqual(self.store.export()["records"], [])

    def test_invalid_revision_does_not_retract_the_old_record(self):
        first = self.assertion()
        with self.assertRaises(ValueError):
            self.store.revise(first, {"value": float("nan")})
        self.assertEqual(self.store.get(first)["status"], "asserted")

    def test_selection_requires_consent_and_verified_observed_evidence(self):
        true = self.verified_experiment()
        user = self.assertion()
        generated = self.store.record("c1", "experiment", {"predicted": True}, [], evidence="generated", status="hypothesis")
        denied = self.store.consolidate("c1", {"training_consent": False})
        self.assertEqual(denied["eligible_ids"], [])
        allowed = self.store.consolidate("c1", {"training_consent": True})
        self.assertEqual(allowed["eligible_ids"], [true])
        self.assertEqual(set(allowed["rejected_ids"]), {user, generated})
        self.assertFalse(allowed["weights_updated"])

    def test_model_versions_rollback_and_training_retraction(self):
        training = self.verified_experiment()
        validation = self.validation()
        first = self.register(training, validation, weights=1, activate=True)
        second = self.register(training, validation, weights=2, activate=True)
        self.assertEqual(self.store.model("qa-model")["id"], second)
        self.store.rollback_model(first)
        self.assertEqual(self.store.model("qa-model")["artifact"]["weights"], [1])
        self.store.retract(training)
        self.assertIsNone(self.store.model("qa-model"))
        with self.assertRaises(ValueError):
            self.store.rollback_model(first)

    def test_activation_requires_an_actual_independent_validation_reference(self):
        training = self.verified_experiment()
        for validation_id in ("", "nonexistent-validation", training):
            with self.subTest(validation_id=validation_id), self.assertRaises(ValueError):
                self.register(training, validation_id, activate=True)

    def test_failed_validation_cannot_be_activated_or_rolled_back(self):
        training = self.verified_experiment()
        validation = self.validation(passed=False)
        metrics = {"passed": False, "retention_passed": True, "validation_id": validation}
        with self.assertRaises(ValueError):
            self.store.register_model("qa-model", {}, [training], metrics, activate=True)
        version = self.store.register_model("qa-model", {}, [training], metrics)
        with self.assertRaises(ValueError):
            self.store.rollback_model(version)

    def test_validation_retraction_invalidates_model_and_sample_overlap_is_rejected(self):
        training = self.verified_experiment()
        validation = self.validation()
        version = self.register(training, validation, activate=True)
        self.store.retract(validation)
        self.assertIsNone(self.store.model("qa-model"))
        with self.assertRaises(ValueError):
            self.store.rollback_model(version)
        overlapping = self.store.record("c1", "test_result", {
            "metrics": {"passed": True, "retention_passed": True}, "sample_ids": ["dataset:qa:training"]
        }, ["dataset:qa:other-reference"], status="verified", evidence="experiment")
        with self.assertRaises(ValueError):
            self.register(training, overlapping, activate=True)

    def test_forget_removes_already_retracted_transitive_payloads(self):
        first = self.assertion("sensitive root")
        dependent = self.store.record("c1", "procedure", {"text": "sensitive derived"}, [first])
        self.store.retract(first)
        result = self.store.forget(first)
        self.assertEqual(set(result["deleted_ids"]), {first, dependent})
        self.assertEqual(self.store.export()["records"], [])
        self.assertTrue(result["backup_deletion_required"])

    def test_backup_restore_preserves_data_and_never_overwrites_existing_files(self):
        first = self.assertion("persisted")
        backup = self.directory / "snapshot.sqlite3"
        info = self.store.backup(backup)
        self.assertEqual(info["sha256"], hashlib.sha256(backup.read_bytes()).hexdigest())
        restored = ExperienceStore.restore(backup, self.directory / "restored.sqlite3")
        self.addCleanup(restored.close)
        self.assertEqual(restored.get(first)["payload"], {"text": "persisted"})
        with self.assertRaises((ValueError, FileExistsError)):
            self.store.backup(backup)
        with self.assertRaises(ValueError):
            ExperienceStore.restore(backup, self.directory / "restored.sqlite3")


class MigrationTests(unittest.TestCase):
    def test_v1_migrates_with_pre_change_backup_and_preserves_record(self):
        with tempfile.TemporaryDirectory(prefix="ar-migration-qa-") as folder:
            path = Path(folder) / "v1.sqlite3"
            create_v1(path)
            store = ExperienceStore(path)
            try:
                self.assertTrue(Path(store.migration_backup).exists())
                with sqlite3.connect(store.migration_backup) as backup:
                    self.assertEqual(backup.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()[0], "1")
                    self.assertEqual(len(backup.execute("PRAGMA table_info(records)").fetchall()), 10)
                self.assertEqual(store.get("E-original")["payload"]["text"], "Dado anterior que deve ser preservado.")
                self.assertEqual(int(store.db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()[0]), SCHEMA_VERSION)
            finally:
                store.close()

    def test_restore_of_old_backup_does_not_modify_the_backup_source(self):
        with tempfile.TemporaryDirectory(prefix="ar-restore-qa-") as folder:
            backup = Path(folder) / "old-backup.sqlite3"
            create_v1(backup)
            original = backup.read_bytes()
            restored = ExperienceStore.restore(backup, Path(folder) / "restored.sqlite3")
            restored.close()
            self.assertEqual(backup.read_bytes(), original)

    def test_existing_legacy_chat_database_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory(prefix="ar-legacy-qa-") as folder:
            path = Path(folder) / "chat.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE conversations(id TEXT PRIMARY KEY,title TEXT)")
                db.execute("INSERT INTO conversations VALUES('original','conversa preservada')")
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                ExperienceStore(path)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
