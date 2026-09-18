"""Tests for the MQTT format extracted from firmware v2.3.3."""

import json
import unittest

from custom_components.mqsolar_local.protocol import (
    mqtt_command_payload,
    mqtt_discovered_topic_base,
    mqtt_topic_base,
)


class ProtocolTest(unittest.TestCase):
    def test_mppt_command_topic(self) -> None:
        self.assertEqual(
            mqtt_topic_base("mppt_charger", "45a", "CHG123456"),
            "mppt_charger_45a/CHG123456",
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


if __name__ == "__main__":
    unittest.main()
