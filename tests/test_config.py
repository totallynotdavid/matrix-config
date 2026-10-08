import json
import tempfile
import unittest
from pathlib import Path

from element_chat.config import load_configuration, load_deployment, load_organization
from element_chat.support import Failure


DEPLOYMENT = {
    "brand": " Acme ",
    "hosts": {
        "chat": "chat.example.com",
        "matrix": "matrix.example.com",
        "account": "account.example.com",
        "admin": "admin.example.com",
    },
}
ORGANIZATION = {
    "administrator": {"username": "admin", "display_name": "Administrator"},
    "space": {"key": "company"},
    "rooms": [
        {"key": "general", "name": "General"},
        {"key": "sales", "name": "Ventas"},
    ],
}


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def write(self, name, value):
        path = self.directory / name
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return path

    def assertRejects(self, loader, name, value, message):
        with self.assertRaisesRegex(Failure, message):
            loader(self.write(name, value))


class RepositoryFilesTest(unittest.TestCase):
    def test_shipped_files_are_valid(self):
        deployment, organization = load_configuration()
        self.assertEqual(set(deployment["urls"]), set(deployment["hosts"]))
        self.assertTrue(organization["rooms"])


class DeploymentTest(ConfigTestCase):
    def mutated(self, change):
        value = json.loads(json.dumps(DEPLOYMENT))
        change(value)
        return value

    def test_valid_file_gets_urls_and_a_stripped_brand(self):
        deployment = load_deployment(self.write("deployment.json", DEPLOYMENT))
        self.assertEqual(deployment["brand"], "Acme")
        self.assertEqual(deployment["urls"]["matrix"], "https://matrix.example.com")

    def test_missing_file(self):
        with self.assertRaisesRegex(Failure, "does not exist"):
            load_deployment(self.directory / "deployment.json")

    def test_invalid_json(self):
        self.assertRejects(load_deployment, "deployment.json", "{", "Invalid JSON")

    def test_not_an_object(self):
        self.assertRejects(load_deployment, "deployment.json", [], "must contain brand")

    def test_extra_key(self):
        value = self.mutated(lambda v: v.update(extra=1))
        self.assertRejects(load_deployment, "deployment.json", value, "must contain brand")

    def test_missing_host(self):
        value = self.mutated(lambda v: v["hosts"].pop("admin"))
        self.assertRejects(load_deployment, "deployment.json", value, "must contain brand")

    def test_hosts_not_an_object(self):
        value = self.mutated(lambda v: v.update(hosts=["a"]))
        self.assertRejects(load_deployment, "deployment.json", value, "must contain brand")

    def test_blank_brand(self):
        value = self.mutated(lambda v: v.update(brand="  "))
        self.assertRejects(load_deployment, "deployment.json", value, "brand must be")

    def test_host_must_be_a_lowercase_dns_name(self):
        for host in ("localhost", "Chat.example.com", "chat_x.example.com", 5):
            with self.subTest(host=host):
                value = self.mutated(lambda v: v["hosts"].update(chat=host))
                self.assertRejects(
                    load_deployment, "deployment.json", value, "lowercase public DNS"
                )

    def test_hosts_must_differ(self):
        value = self.mutated(lambda v: v["hosts"].update(admin="chat.example.com"))
        self.assertRejects(load_deployment, "deployment.json", value, "must be unique")


class OrganizationTest(ConfigTestCase):
    def mutated(self, change):
        value = json.loads(json.dumps(ORGANIZATION))
        change(value)
        return value

    def test_valid_file(self):
        path = self.write("organization.json", ORGANIZATION)
        self.assertEqual(load_organization(path), ORGANIZATION)

    def test_missing_file(self):
        with self.assertRaisesRegex(Failure, "does not exist"):
            load_organization(self.directory / "organization.json")

    def test_invalid_json(self):
        self.assertRejects(load_organization, "organization.json", "{", "Invalid JSON")

    def test_not_an_object(self):
        self.assertRejects(
            load_organization, "organization.json", [], "must contain administrator"
        )

    def test_missing_section(self):
        for section in ORGANIZATION:
            with self.subTest(section=section):
                value = self.mutated(lambda v: v.pop(section))
                self.assertRejects(
                    load_organization, "organization.json", value, "must contain administrator"
                )

    def test_administrator_keys(self):
        value = self.mutated(lambda v: v["administrator"].pop("display_name"))
        self.assertRejects(
            load_organization, "organization.json", value, "administrator must contain"
        )

    def test_administrator_display_name(self):
        value = self.mutated(lambda v: v["administrator"].update(display_name=" "))
        self.assertRejects(load_organization, "organization.json", value, "display_name")

    def test_space_keys(self):
        value = self.mutated(lambda v: v.update(space={"name": "x"}))
        self.assertRejects(load_organization, "organization.json", value, "space must contain")

    def test_rooms_must_be_a_non_empty_list(self):
        for rooms in ([], {}, "general"):
            with self.subTest(rooms=rooms):
                value = self.mutated(lambda v: v.update(rooms=rooms))
                self.assertRejects(
                    load_organization, "organization.json", value, "rooms must be a non-empty list"
                )

    def test_room_keys(self):
        value = self.mutated(lambda v: v["rooms"][1].pop("name"))
        self.assertRejects(
            load_organization, "organization.json", value, r"rooms\[1\] must contain key and name"
        )

    def test_room_name(self):
        value = self.mutated(lambda v: v["rooms"][0].update(name=""))
        self.assertRejects(
            load_organization, "organization.json", value, r"rooms\[0\] name must be"
        )

    def test_keys_must_be_alias_safe(self):
        changes = {
            "administrator username": lambda v: v["administrator"].update(username="Admin"),
            "space key": lambda v: v["space"].update(key="my space"),
            r"rooms\[1\] key": lambda v: v["rooms"][1].update(key="ventas:es"),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                self.assertRejects(
                    load_organization,
                    "organization.json",
                    self.mutated(change),
                    f"{label} must use only",
                )

    def test_key_must_be_a_string(self):
        value = self.mutated(lambda v: v["rooms"][0].update(key=7))
        self.assertRejects(load_organization, "organization.json", value, "must use only")

    def test_space_and_room_keys_must_differ(self):
        for change in (
            lambda v: v["rooms"][1].update(key="general"),
            lambda v: v["space"].update(key="general"),
        ):
            with self.subTest():
                self.assertRejects(
                    load_organization,
                    "organization.json",
                    self.mutated(change),
                    "keys must be unique",
                )


if __name__ == "__main__":
    unittest.main()
