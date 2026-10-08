import tempfile
import unittest
from pathlib import Path

from element_chat.support import ORGANIZATION, Failure
from element_chat.users import validate_worker_file


HEADER = "username,display_name,teams\n"
TEAMS = {"general", "sales"}


class ValidateWorkerFileTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def worker_file(self, text, mode=0o600):
        path = self.directory / "workers.csv"
        path.write_text(text)
        path.chmod(mode)
        return path

    def assertRejects(self, text, message, **options):
        with self.assertRaisesRegex(Failure, message):
            validate_worker_file(self.worker_file(text, **options), TEAMS)

    def test_valid_file_returns_normalized_rows(self):
        path = self.worker_file(
            HEADER + "alice, Alicia Pérez ,sales\nbob,Roberto Díaz,sales; general;\n"
        )
        self.assertEqual(
            validate_worker_file(path, TEAMS),
            [
                {"username": "alice", "display_name": "Alicia Pérez", "teams": ["sales"]},
                {
                    "username": "bob",
                    "display_name": "Roberto Díaz",
                    "teams": ["sales", "general"],
                },
            ],
        )

    def test_file_inside_the_repository(self):
        with self.assertRaisesRegex(Failure, "outside the repository"):
            validate_worker_file(ORGANIZATION, TEAMS)

    def test_file_readable_by_others(self):
        for mode in (0o640, 0o604, 0o660, 0o644):
            with self.subTest(mode=oct(mode)):
                self.assertRejects(HEADER + "alice,Alicia,sales\n", "mode 0600", mode=mode)

    def test_wrong_columns(self):
        for header in ("username,display_name\n", "name,display_name,teams\n"):
            with self.subTest(header=header):
                self.assertRejects(header + "alice,Alicia,sales\n", "columns must be exactly")

    def test_no_rows(self):
        self.assertRejects(HEADER, "is empty")

    def test_short_row(self):
        self.assertRejects(HEADER + "alice,Alicia\n", "Malformed CSV row 2")

    def test_long_row(self):
        self.assertRejects(HEADER + "alice,Alicia,sales,extra\n", "Malformed CSV row 2")

    def test_invalid_username(self):
        for username in ("Alice", "al ice", "alice@x", ""):
            with self.subTest(username=username):
                self.assertRejects(
                    HEADER + f'"{username}",Alicia,sales\n', "Invalid username on line 2"
                )

    def test_duplicate_username(self):
        self.assertRejects(
            HEADER + "alice,Alicia,sales\nalice,Alicia B,general\n",
            "Duplicate username on line 3: alice",
        )

    def test_display_name_required(self):
        self.assertRejects(HEADER + "alice,  ,sales\n", "Display name is required on line 2")

    def test_team_required(self):
        for teams in ("", " ; "):
            with self.subTest(teams=teams):
                self.assertRejects(
                    HEADER + f'alice,Alicia,"{teams}"\n', "At least one team is required on line 2"
                )

    def test_unknown_team(self):
        self.assertRejects(
            HEADER + "alice,Alicia,sales;ops;hr\n", "Unknown team on line 2: hr, ops"
        )


if __name__ == "__main__":
    unittest.main()
