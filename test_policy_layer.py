import unittest

from ast_guard import inspect_code_safety
from policy import PolicyError, get_profile, load_policies, _validate_profile


class TestImportAllowlist(unittest.TestCase):
    def test_without_allowlist_legacy_behavior_unchanged(self):
        self.assertEqual(inspect_code_safety("import requests\nrequests.get('https://pypi.org')"), [])
        self.assertTrue(inspect_code_safety("import os\nos.system('ls')"))
        self.assertTrue(inspect_code_safety("e = eval\ne('1+1')"))
        self.assertTrue(inspect_code_safety("imp = __import__\nimp('os')"))

    def test_listed_imports_pass(self):
        self.assertEqual(inspect_code_safety("import math\nprint(math.sqrt(4))", allowed_imports={"math"}), [])
        self.assertEqual(
            inspect_code_safety("from collections import Counter\nprint(Counter('aab'))", allowed_imports={"collections"}),
            [],
        )

    def test_unlisted_import_rejected(self):
        violations = inspect_code_safety("import json", allowed_imports={"math"})
        self.assertTrue(any("not permitted by policy" in v for v in violations))

    def test_from_import_of_unlisted_module_rejected(self):
        violations = inspect_code_safety("from json import dumps", allowed_imports={"math"})
        self.assertTrue(any("not permitted by policy" in v for v in violations))

    def test_submodule_judged_by_top_level_package(self):
        self.assertEqual(inspect_code_safety("import urllib.request", allowed_imports={"urllib"}), [])
        self.assertTrue(inspect_code_safety("import urllib.request", allowed_imports={"math"}))

    def test_relative_import_rejected_when_allowlist_active(self):
        self.assertTrue(inspect_code_safety("from . import helper", allowed_imports={"math"}))

    def test_empty_allowlist_rejects_every_import(self):
        self.assertTrue(inspect_code_safety("import math", allowed_imports=set()))

    def test_importlib_route_is_closed_only_by_the_allowlist(self):
        code = "import importlib\nprint(importlib.import_module('math').sqrt(4))"
        # 特征测试：单靠黑名单，这条路径不会被标记
        self.assertEqual(inspect_code_safety(code), [])
        # 白名单里没有 importlib 时被拒绝
        self.assertTrue(inspect_code_safety(code, allowed_imports={"math"}))


class TestPolicyLoading(unittest.TestCase):
    def test_shipped_policy_file_loads_and_validates(self):
        profiles = load_policies()
        self.assertIn("offline_default", profiles)
        self.assertIn("web_whitelisted", profiles)

    def test_offline_profile_has_no_network(self):
        self.assertEqual(get_profile("offline_default")["network"], "none")

    def test_unknown_profile_refused(self):
        with self.assertRaises(PolicyError):
            get_profile("does_not_exist")

    def test_missing_or_invalid_profile_name_refused(self):
        for bad in (None, "", 123):
            with self.assertRaises(PolicyError):
                get_profile(bad)

    def test_missing_policy_file_refused(self):
        with self.assertRaises(PolicyError):
            load_policies("/nonexistent/policies.json")


class TestProfileValidation(unittest.TestCase):
    def _good(self):
        return dict(get_profile("offline_default"))

    def test_good_profile_passes(self):
        _validate_profile("ok", self._good())

    def test_policy_cannot_grant_a_module_the_guard_bans(self):
        p = self._good()
        p["allowed_imports"] = ["math", "os"]
        with self.assertRaises(PolicyError):
            _validate_profile("bad", p)

    def test_unknown_key_rejected(self):
        p = self._good()
        p["privileged"] = True
        with self.assertRaises(PolicyError):
            _validate_profile("bad", p)

    def test_missing_key_rejected(self):
        p = self._good()
        del p["memory"]
        with self.assertRaises(PolicyError):
            _validate_profile("bad", p)

    def test_out_of_range_or_malformed_values_rejected(self):
        cases = [
            ("network", "host"),
            ("image", "x --privileged"),
            ("image", "--privileged"),
            ("memory", "lots"),
            ("memory", "0m"),
            ("cpus", 0),
            ("cpus", 99),
            ("cpus", True),
            ("timeout_seconds", 0),
            ("timeout_seconds", 9999),
            ("timeout_seconds", True),
            ("allowed_imports", "math"),
        ]
        for key, value in cases:
            p = self._good()
            p[key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(PolicyError):
                    _validate_profile("bad", p)


if __name__ == "__main__":
    unittest.main()
