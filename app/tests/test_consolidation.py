"""Contratos de consolidação, sem rede e sem credenciais."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ModelContract(unittest.TestCase):
    def test_capabilities_are_specific_to_the_model_and_validate_configuration(self):
        from core.provider_registry import capabilities
        records = {"openai:text-small": {"images": False, "tools": False, "structured": False}}
        cfg = Mock(get=lambda key, default=None: records if key == "providers.model_capabilities" else default)
        with patch("core.config.get_config", return_value=cfg):
            self.assertFalse(capabilities("openai:text-small").tools)
            self.assertTrue(capabilities("openai:another-model").tools)
            records["openai:text-small"]["tools"] = "yes"
            with self.assertRaises(ValueError):
                capabilities("openai:text-small")

    def test_rsi_decision_requires_explicit_confirmation_at_rpc_boundary(self):
        from desktop.bridge_core import BridgeCore
        import json
        with patch("core.rsi.decide") as decision:
            result = json.loads(BridgeCore.rsiDecide(Mock(), "file-v2", "promover", False))
        self.assertFalse(result["ok"])
        decision.assert_not_called()
