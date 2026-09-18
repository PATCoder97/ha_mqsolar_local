"""Isolated logic regression tests; not a substitute for HA integration tests.

Execute actual function/class ASTs with injected collaborators so the suite can
run without installing Home Assistant. No hardware or MQTT broker is contacted.
"""
import ast
import asyncio
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).parents[1] / "custom_components/mqsolar_local"


class HAError(Exception):
    pass


def load_logic(filename, namespace):
    tree = ast.parse((ROOT / filename).read_text())
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    ast.fix_missing_locations(tree)
    exec(compile(tree, filename, "exec"), namespace)
    return namespace


class ControlTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hardware = {"chargeMode": 0, "maxCurrent": 10.0, "maxVoltage": 14.4,
                         "maxChargeCurrent": 45.0, "maxChargeVoltage": 60.0}
        self.writes = []
        self.reject = False
        self.fail_readback = False
        self.coordinator = SimpleNamespace(data={"_device_type": "Charger"}, config_lock=asyncio.Lock())
        self.coordinator.async_set_updated_data = lambda data: setattr(self.coordinator, "data", data)

        async def read(*args):
            await asyncio.sleep(0)
            if self.fail_readback and self.writes:
                raise HAError("timeout")
            return {"parameter": dict(self.hardware)}

        async def write(hass, coordinator, topic, mode, current, voltage):
            await asyncio.sleep(0)
            self.writes.append((mode, current, voltage))
            if not self.reject:
                self.hardware.update(chargeMode=mode, maxCurrent=current, maxVoltage=voltage)

        self.logic = load_logic("control.py", {
            "math": math, "asyncio": asyncio, "HomeAssistantError": HAError,
            "DEFAULT_MQTT_TOPIC_CODE": "45a",
            "async_get_charger_config": read, "async_set_charger_config": write,
        })

    async def change(self, key, value):
        await self.logic["async_change_config"](None, self.coordinator, key, value)

    async def test_reads_fresh_values_before_change(self):
        self.coordinator.data["_charger_config"] = dict(self.hardware, maxVoltage=12.0)
        await self.change("maxCurrent", 11.0)
        self.assertEqual(self.writes, [(0, 11.0, 14.4)])

    async def test_concurrent_changes_preserve_both_values(self):
        await asyncio.gather(self.change("maxCurrent", 11.0), self.change("maxVoltage", 14.5))
        self.assertEqual(self.hardware["maxCurrent"], 11.0)
        self.assertEqual(self.hardware["maxVoltage"], 14.5)

    async def test_service_updates_cache_and_later_entity_preserves_values(self):
        await self.logic["async_write_config"](None, self.coordinator, "45a", 1, 12.0, 14.6)
        self.assertEqual(self.coordinator.data["_charger_config"]["maxVoltage"], 14.6)
        await self.change("maxCurrent", 13.0)
        self.assertEqual(self.writes[-1], (1, 13.0, 14.6))

    async def test_rejected_write_displays_actual_values(self):
        self.reject = True
        with self.assertRaises(HAError):
            await self.change("maxCurrent", 11.0)
        self.assertEqual(self.coordinator.data["_charger_config"]["maxCurrent"], 10.0)

    async def test_timeout_invalidates_cache(self):
        self.fail_readback = True
        with self.assertRaises(HAError):
            await self.change("maxCurrent", 11.0)
        self.assertIsNone(self.coordinator.data["_charger_config"])

    async def test_device_limits_and_nonfinite_values_rejected(self):
        for value in (46.0, -1.0, float("nan"), float("inf")):
            with self.assertRaises(HAError):
                await self.change("maxCurrent", value)
        self.assertEqual(self.writes, [])

    async def test_inverter_cannot_receive_charger_config(self):
        self.coordinator.data["_device_type"] = "Inverter"
        with self.assertRaises(HAError):
            await self.change("maxCurrent", 11.0)
        self.assertEqual(self.writes, [])

    def test_invalid_config_response(self):
        for value in (None, "bad", float("nan"), -1):
            with self.assertRaises(HAError):
                self.logic["_parse_config"](dict(self.hardware, maxVoltage=value))


class DataTest(unittest.TestCase):
    def setUp(self):
        protocol = load_logic("protocol.py", {})
        self.api = load_logic("api.py", {"MQTT_CHARGER_FIELDS": protocol["MQTT_CHARGER_FIELDS"], "REQUEST_TIMEOUT": 5})

    def normalize(self, data):
        return self.api["MQSolarLocalApi"]._normalize(data, {"deviceId": "test"})

    def test_flat_snake_case(self):
        result = self.normalize({"pv_voltage": 40.0, "bat_voltage": 12.34})
        self.assertEqual(result["charger"]["batVoltage"], 12.34)

    def test_nested_and_canonical_precedence(self):
        result = self.normalize({"charger": {"bat_voltage": 12.0, "batVoltage": 12.34}})
        self.assertEqual(result["charger"]["batVoltage"], 12.34)

    def test_inverter_alias(self):
        self.assertEqual(self.normalize({"dc_voltage": 40.0})["inverter"]["dcVoltage"], 40.0)

    def test_invalid_section(self):
        with self.assertRaises(self.api["MQSolarInvalidResponseError"]):
            self.normalize({"charger": None})

    def test_missing_data_sensor_and_diagnostics(self):
        tree = ast.parse((ROOT / "sensor.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MQSolarSensor")
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "native_value")
        fn.decorator_list = []
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), fn], type_ignores=[])
        ast.fix_missing_locations(module)
        ns = {}; exec(compile(module, "sensor.py", "exec"), ns)
        desc = SimpleNamespace(path=None, status_key=False, section="charger", key="batVoltage")
        entity = SimpleNamespace(entity_description=desc, coordinator=SimpleNamespace(data={
            "hasData": False, "charger": {"batVoltage": 12.34}, "_status": {"rssi": -50}}))
        self.assertIsNone(ns["native_value"](entity))
        desc.status_key = True; desc.key = "rssi"
        self.assertEqual(ns["native_value"](entity), -50)


class MQTTTest(unittest.IsolatedAsyncioTestCase):
    async def test_retained_config_ignored_and_subscription_cleaned_up(self):
        callback = None
        cleaned = []

        async def subscribe(hass, topic, handler, **kwargs):
            nonlocal callback
            callback = handler
            # An old retained response arrives immediately on subscription.
            await handler(SimpleNamespace(retain=True, payload=json.dumps({
                "command": "charger_config_sync", "maxVoltage": 99})))
            return lambda: cleaned.append(True)

        async def publish(*args, **kwargs):
            await callback(SimpleNamespace(retain=False, payload=json.dumps({
                "command": "charger_config_sync", "maxVoltage": 14.4})))

        ns = load_logic("mqtt_commands.py", {
            "asyncio": asyncio, "json": json, "async_subscribe": subscribe,
            "async_publish": publish, "mqtt_command_payload": lambda *args: "{}",
            "MQTT_RESPONSE_TIMEOUT": 1, "HomeAssistantError": HAError,
        })
        coordinator = SimpleNamespace(data={"_mqtt_topic_base": "45a_45a/test"})
        result = await ns["async_get_charger_config"](
            SimpleNamespace(loop=asyncio.get_running_loop()), coordinator, "45a")
        self.assertEqual(result["maxVoltage"], 14.4)
        self.assertEqual(cleaned, [True])

    async def test_inverter_does_not_subscribe_to_charger_telemetry(self):
        ns = load_logic("mqtt_commands.py", {})
        unsubscribe = await ns["async_subscribe_telemetry"](
            None, SimpleNamespace(data={"_device_id": "inv", "_device_type": "Inverter"}))
        unsubscribe()
