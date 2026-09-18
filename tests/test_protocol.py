"""Tests for the MQTT format extracted from firmware v2.3.3."""

import json
import importlib.util
from pathlib import Path
import unittest

# Load the pure helper without executing the HA-dependent package __init__.
spec = importlib.util.spec_from_file_location(
    "mq_protocol", Path(__file__).parents[1] / "custom_components/mqsolar_local/protocol.py"
)
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)
mqtt_charger_measurements = protocol.mqtt_charger_measurements
mqtt_command_payload = protocol.mqtt_command_payload
mqtt_discovered_topic_base = protocol.mqtt_discovered_topic_base
mqtt_topic_base = protocol.mqtt_topic_base
normalize_status_text = protocol.normalize_status_text


class ProtocolTest(unittest.TestCase):
    def test_mppt_command_topic(self) -> None:
        self.assertEqual(
            mqtt_topic_base("mppt_charger", "45a", "CHG123456"),
            "mppt_charger_45a/CHG123456",
        )

    def test_observed_v233_configured_topic(self) -> None:
        self.assertEqual(
            mqtt_topic_base("45a", "45a", "CHG14681307"),
            "45a_45a/CHG14681307",
        )

    def test_restart_payload(self) -> None:
        self.assertEqual(mqtt_command_payload("restart"), '{"command":"restart"}')

    def test_discovered_topic_base(self) -> None:
        self.assertEqual(
            mqtt_discovered_topic_base("45a_45a/CHG14681307/data", "CHG14681307"),
            "45a_45a/CHG14681307",
        )

    def test_discovered_topic_rejects_another_device(self) -> None:
        self.assertIsNone(
            mqtt_discovered_topic_base("45a_45a/CHG00000000/data", "CHG14681307")
        )

    def test_mqtt_charger_measurements(self) -> None:
        self.assertEqual(
            mqtt_charger_measurements(
                {"pv_voltage": 40.3, "bat_current": 0.478, "ignored": 1}
            ),
            {"pvVoltage": 40.3, "batCurrent": 0.478},
        )

    def test_set_charger_config_payload(self) -> None:
        payload = mqtt_command_payload(
            "set_charger_config",
            {"chargeMode": 1, "maxCurrent": 45.0, "maxVoltage": 14.4},
        )
        self.assertEqual(
            json.loads(payload),
            {
                "command": "set_charger_config",
                "parameter": {
                    "chargeMode": 1,
                    "maxCurrent": 45.0,
                    "maxVoltage": 14.4,
                },
            },
        )

    def test_normalize_status_text(self) -> None:
        self.assertEqual(normalize_status_text("CHARGING"), "Charging")
        self.assertEqual(normalize_status_text("UNKNOWN"), "Not charging")
        self.assertEqual(normalize_status_text("FAULT_LOW"), "Low voltage fault")
        self.assertEqual(normalize_status_text("FAULT_HIGH"), "High voltage fault")
        self.assertEqual(normalize_status_text("new_state"), "Unknown")
        self.assertIsNone(normalize_status_text(None))


if __name__ == "__main__":
    unittest.main()
