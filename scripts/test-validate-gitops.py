#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("validator", pathlib.Path(__file__).with_name("validate-gitops.py"))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ValidationGateTests(unittest.TestCase):
    def test_public_ssh_is_rejected(self):
        with self.assertRaises(AssertionError):
            validator.validate_rendered('apiVersion: v1\nkind: Service\nmetadata: {name: test}\nspec:\n  type: LoadBalancer\n  ports: [{port: 22, targetPort: ssh}]\n')

    def test_direct_intake_deployment_is_rejected(self):
        with self.assertRaises(AssertionError):
            validator.check_source({"repoURL": "https://github.com/jshipster-io/gitops.git", "targetRevision": "main"})

    def test_plaintext_secret_is_rejected(self):
        with self.assertRaises(AssertionError):
            validator.validate_rendered('apiVersion: v1\nkind: Secret\nmetadata: {name: test}\nstringData: {password: example}\n')

    def test_invalid_kubernetes_field_type_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validator.validate_rendered('apiVersion: v1\nkind: Service\nmetadata: {name: test}\nspec:\n  ports: [{port: "not-a-number"}]\n')

    def test_unknown_resource_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validator.validate_rendered('apiVersion: example.invalid/v1\nkind: TypoResource\nmetadata: {name: test}\n')


if __name__ == "__main__":
    unittest.main()
