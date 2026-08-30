import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


GIP = Path(__file__).with_name("gip")


class GipIntegrationTest(unittest.TestCase):
    def test_archives_exactly_git_visible_worktree_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()
            self.run_command(repo, "git", "init", "-q")
            self.run_command(repo, "git", "config", "user.email", "test@example.com")
            self.run_command(repo, "git", "config", "user.name", "Test")

            (repo / ".gitignore").write_text("*.log\nbuild/\n")
            (repo / "tracked.txt").write_text("committed\n")
            (repo / "tracked.log").write_text("tracked despite ignore\n")
            (repo / "deleted.txt").write_text("delete me\n")
            (base / "outside.txt").write_text("must not leak\n")
            has_symlink = True
            try:
                (repo / "outside-link").symlink_to("../outside.txt")
            except OSError:
                has_symlink = False

            tracked = [
                ".gitignore",
                "tracked.txt",
                "deleted.txt",
            ]
            if has_symlink:
                tracked.append("outside-link")
            self.run_command(repo, "git", "add", *tracked)
            self.run_command(repo, "git", "add", "-f", "tracked.log")
            self.run_command(repo, "git", "commit", "-qm", "fixture")

            (repo / "tracked.txt").write_text("working tree\n")
            (repo / "deleted.txt").unlink()
            (repo / "keep.txt").write_text("keep\n")
            (repo / "ignored.log").write_text("ignore\n")
            (repo / "-dash").write_text("dash\n")
            (repo / "line\nbreak").write_text("newline\n")
            (repo / "build").mkdir()
            (repo / "build" / "artifact").write_text("ignore\n")
            (repo / "empty").mkdir()

            nested = repo / "nested"
            nested.mkdir()
            (nested / ".gitignore").write_text("secret*\n!secret-keep\n")
            (nested / "keep").write_text("keep\n")
            (nested / "secret").write_text("ignore\n")
            (nested / "secret-keep").write_text("keep\n")

            (repo / ".git" / "info" / "exclude").write_text("info.tmp\n")
            (repo / "info.tmp").write_text("ignore\n")
            global_ignore = base / "global-ignore"
            global_ignore.write_text("global.tmp\n")
            (repo / "global.tmp").write_text("ignore\n")
            self.run_command(repo, "git", "config", "core.excludesFile", str(global_ignore))

            output = repo / "output.zip"
            output.write_bytes(b"old archive must not include itself")
            result = self.run_command(nested, sys.executable, str(GIP), str(output))
            expected = {
                ".gitignore",
                "-dash",
                "keep.txt",
                "line\nbreak",
                "nested/.gitignore",
                "nested/keep",
                "nested/secret-keep",
                "tracked.log",
                "tracked.txt",
            }
            if has_symlink:
                expected.add("outside-link")
            self.assertIn(f"({len(expected)} files)", result.stdout)

            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), expected)
                self.assertEqual(archive.read("tracked.txt"), b"working tree\n")
                if has_symlink:
                    link = archive.getinfo("outside-link")
                    self.assertTrue(stat.S_ISLNK(link.external_attr >> 16))
                    self.assertEqual(archive.read("outside-link"), b"../outside.txt")
                    self.assertNotIn(b"must not leak", archive.read("outside-link"))

    def test_does_not_follow_symlinked_parents_or_output_aliases(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()
            self.run_command(repo, "git", "init", "-q")
            self.run_command(repo, "git", "config", "user.email", "test@example.com")
            self.run_command(repo, "git", "config", "user.name", "Test")

            tracked_dir = repo / "dir"
            tracked_dir.mkdir()
            (tracked_dir / "secret").write_text("inside\n")
            self.run_command(repo, "git", "add", "dir/secret")
            self.run_command(repo, "git", "commit", "-qm", "fixture")

            (tracked_dir / "secret").unlink()
            tracked_dir.rmdir()
            outside = base / "outside"
            outside.mkdir()
            (outside / "secret").write_text("OUTSIDE LEAK\n")
            archives = repo / "archives"
            archives.mkdir()
            output = archives / "output.zip"
            output.write_bytes(b"OLD ARCHIVE")
            try:
                tracked_dir.symlink_to(outside, target_is_directory=True)
                (repo / "output-alias").symlink_to("archives", target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")

            self.run_command(
                repo,
                sys.executable,
                str(GIP),
                str(repo / "output-alias" / "output.zip"),
            )

            with zipfile.ZipFile(output) as archive:
                self.assertNotIn("dir/secret", archive.namelist())
                self.assertNotIn("archives/output.zip", archive.namelist())
                for name in archive.namelist():
                    self.assertNotEqual(archive.read(name), b"OUTSIDE LEAK\n")
                    self.assertNotEqual(archive.read(name), b"OLD ARCHIVE")

    @staticmethod
    def run_command(cwd, *command):
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


if __name__ == "__main__":
    unittest.main()
