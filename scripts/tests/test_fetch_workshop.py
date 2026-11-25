"""Tests for the `bootstrap` skill's `fetch-workshop.sh`."""

import os
import subprocess
import tempfile
import unittest

import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILL = os.path.join(ROOT, ".apm", "skills", "bootstrap")
SCRIPT = os.path.join(SKILL, "scripts", "fetch-workshop.sh")
TEMPLATES = sorted(f[: -len(".yaml")] for f in os.listdir(os.path.join(SKILL, "assets", "workshops")))
TAG = "workshop-v9.9.9"

# Stands in for `curl -fsSL -o DEST URL`: serves the URL's path below the tag
# from this working tree, and logs the URL.
FAKE_CURL = """#!/bin/sh
eval "dest=\\${$(($# - 1))}"
eval "url=\\${$#}"
echo "$url" >> "$CURL_LOG"
cp "$REPO/${url#*/agent-collections/*/}" "$dest"
"""


class FetchWorkshopTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        bin_dir = os.path.join(self.tmp, "bin")
        os.mkdir(bin_dir)
        with open(os.path.join(bin_dir, "curl"), "w") as f:
            f.write(FAKE_CURL)
        os.chmod(os.path.join(bin_dir, "curl"), 0o755)
        self.log = os.path.join(self.tmp, "curl.log")
        self.env = {
            **os.environ,
            "PATH": bin_dir + os.pathsep + os.environ["PATH"],
            "REPO": os.path.abspath(ROOT),
            "CURL_LOG": self.log,
        }

    def fetch(self, project: str, template: str) -> subprocess.CompletedProcess:
        path = os.path.join(self.tmp, project)
        os.makedirs(path, exist_ok=True)
        return subprocess.run(
            ["sh", SCRIPT, TAG, template], cwd=path, env=self.env, capture_output=True, text=True
        )

    def test_every_template_yields_a_workshop_with_its_project_sdks(self):
        for template in TEMPLATES:
            with self.subTest(template=template):
                result = self.fetch(f"my-{template}-project", template)
                self.assertEqual(result.returncode, 0, result.stderr)
                workshop_dir = os.path.join(self.tmp, f"my-{template}-project", ".workshop")
                with open(os.path.join(workshop_dir, f"my-{template}-project.yaml")) as f:
                    workshop = yaml.safe_load(f)
                self.assertEqual(workshop["name"], f"my-{template}-project")
                for sdk in workshop["sdks"]:
                    if sdk["name"].startswith("project-"):
                        local = sdk["name"][len("project-") :]
                        with open(os.path.join(workshop_dir, local, "sdk.yaml")) as f:
                            self.assertEqual(yaml.safe_load(f)["name"], local)

    def test_fetches_only_from_the_given_tag(self):
        self.assertEqual(self.fetch("proj", TEMPLATES[0]).returncode, 0)
        with open(self.log) as f:
            urls = f.read().split()
        self.assertTrue(urls)
        for url in urls:
            self.assertIn(f"/agent-collections/{TAG}/", url)

    def test_refuses_to_overwrite_an_existing_workshop(self):
        existing = os.path.join(self.tmp, "proj", ".workshop", "proj.yaml")
        os.makedirs(os.path.dirname(existing))
        with open(existing, "w") as f:
            f.write("mine\n")
        result = self.fetch("proj", TEMPLATES[0])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        with open(existing) as f:
            self.assertEqual(f.read(), "mine\n")
        self.assertEqual(os.listdir(os.path.dirname(existing)), ["proj.yaml"])

    def test_rejects_a_directory_name_workshop_does_not_accept(self):
        for project in ("My_Project", "2fast", "trailing-", "a" * 41):
            with self.subTest(project=project):
                result = self.fetch(project, TEMPLATES[0])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not a valid workshop name", result.stderr)
                self.assertFalse(os.path.exists(os.path.join(self.tmp, project, ".workshop")))

    def test_fails_without_writing_when_a_download_fails(self):
        result = self.fetch("proj", "no-such-template")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "proj", ".workshop")))


if __name__ == "__main__":
    unittest.main()
