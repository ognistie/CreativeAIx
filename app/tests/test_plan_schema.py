"""Contrato tipado do plano (core/plan_schema.py): forma no schema, regras no validador.

Inclui um teste de propriedade: centenas de planos malformados gerados nunca derrubam o validador e nunca
são aprovados.
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.plan_schema import SCHEMA_VERSION, plan_json_schema, plan_shape, steps_shape
from core.plan_validator import validate_plan, validate_steps

GOOD = {"subtasks": [{"agent": "FILE", "task": "organizar a pasta Downloads", "params": {}}]}


def _policies(check):
    return [v["policy"] for v in check.violations]


class PlanShape(unittest.TestCase):
    def test_good_plan_passes_and_extras_are_kept(self):
        plan = dict(GOOD, analysis="x", fast_path="perfil")
        self.assertEqual(plan_shape(plan), (None, {}))
        self.assertTrue(validate_plan("organizar a pasta Downloads", plan).approved)

    def test_whole_plan_errors_keep_their_literal_messages(self):
        self.assertEqual(plan_shape([])[0], "plano deve ser um objeto")
        self.assertEqual(plan_shape({})[0], "plano sem subtasks")
        self.assertEqual(plan_shape({"subtasks": [GOOD["subtasks"][0]] * 6})[0],
                         "subtasks deve ser uma lista de ate cinco objetos")

    def test_subtask_types(self):
        cases = [({"agent": 1, "task": "x"}, "POL-000"), ({"agent": "FILE", "params": None}, "POL-000"),
                 ({"agent": "FILE", "params": "a=1"}, "POL-000"), ({"agent": "FILE", "depends_on": True}, "POL-004"),
                 ({"agent": "FILE", "depends_on": "1"}, "POL-004")]
        for sub, policy in cases:
            with self.subTest(sub=sub):
                check = validate_plan("organizar", {"subtasks": [sub]})
                self.assertFalse(check.approved)
                self.assertIn(policy, _policies(check))

    def test_depends_on_must_point_back(self):
        sub = dict(GOOD["subtasks"][0])
        check = validate_plan("organizar a pasta Downloads", {"subtasks": [sub, dict(sub, depends_on=2)]})
        self.assertIn("POL-004", _policies(check))

    def test_steps_shape(self):
        self.assertEqual(steps_shape([]), "agente nao propos nenhum passo")
        self.assertIsNotNone(steps_shape([{"action": "click", "params": None}]))
        self.assertIsNotNone(steps_shape(["click"]))
        self.assertIsNone(steps_shape([{"action": "click"}]))
        self.assertFalse(validate_steps("DESKTOP", {}, [{"action": "hotkey", "params": []}], "x").approved)

    def test_json_schema_documents_the_contract(self):
        schema = plan_json_schema()
        self.assertEqual(SCHEMA_VERSION, 1)
        self.assertIn("subtasks", schema["properties"])
        self.assertEqual(schema["properties"]["subtasks"]["maxItems"], 5)


class MalformedPlansProperty(unittest.TestCase):
    """Propriedade: plano malformado nunca levanta exceção e nunca é aprovado."""

    JUNK = [None, True, 0, 3.5, "", "x", [], {}, ["a"], {"a": 1}]

    def mutate(self, rng):
        sub = {"agent": "FILE", "task": "organizar a pasta Downloads", "params": {}}
        key = rng.choice(["agent", "task", "params", "depends_on"])
        value = rng.choice(self.JUNK)
        if key in ("agent", "task") and isinstance(value, str):
            value = 7
        if key == "params" and isinstance(value, dict):
            value = [value]
        if key == "depends_on" and value in (None, 0):
            value = "1"
        sub[key] = value
        shape = rng.randrange(4)
        if shape == 0:
            return rng.choice(self.JUNK[:7] + [[sub]])
        if shape == 1:
            return {"subtasks": [sub] * rng.randint(6, 9)}
        if shape == 2:
            return {"subtasks": [sub, rng.choice(self.JUNK[:7])]}
        return {"subtasks": [sub]}

    def test_generated_plans_are_rejected(self):
        rng = random.Random(20261125)
        for n in range(1000):
            plan = self.mutate(rng)
            with self.subTest(n=n, plan=plan):
                self.assertFalse(validate_plan("organizar a pasta Downloads", plan).approved)


if __name__ == "__main__":
    unittest.main()
