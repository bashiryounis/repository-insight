import os
import fnmatch
import logging
from src.utils.helper import get_tree

logger = logging.getLogger(__name__)

class GitRepoParser:
    import pygit2
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.repo = pygit2.Repository(repo_path)
        self.nodes = {
            "metadata": {},
            "folders": [],
            "files": [],
            "branches": [],
            "commits": [],
        }

    def get_nodes(self):
        self.get_metadata()

        try:
            head_commit = self.repo[self.repo.head.target]
            folders, files = self.get_tree_dicts(head_commit)
            self.nodes["folders"] = folders
            self.nodes["files"] = files
        except Exception as e:
            logger.warning(f"Failed to extract tree from HEAD commit: {e}")

        try:
            self.get_branches()
            self.collect_all_commits()
        except Exception as e:
            logger.warning(f"Failed to collect branches or commits: {e}")

        return self.nodes

    def _get_tree_from_commit(self, commit_oid) -> str:
        commit = self.repo[commit_oid]
        tree = commit.tree
        lines = []

        def walk(tree, prefix=""):
            entries = sorted(tree, key=lambda e: e.name)
            for i, entry in enumerate(entries):
                if any(fnmatch.fnmatch(entry.name, pat) for pat in [".git", "__pycache__", "*.pyc", "*.pyo", ".DS_Store"]):
                    continue
                connector = "└── " if i == len(entries) - 1 else "├── "
                lines.append(prefix + connector + entry.name)
                if entry.filemode == pygit2.GIT_FILEMODE_TREE:
                    subtree = self.repo[entry.id]
                    extension_prefix = prefix + ("    " if i == len(entries) - 1 else "│   ")
                    walk(subtree, extension_prefix)

        walk(tree)
        return "\n".join(lines)

    def get_metadata(self):
        remote_url = None
        repo_name = None

        try:
            remote = self.repo.remotes["origin"]
            if remote:
                remote_url = remote.url
                repo_name = os.path.splitext(os.path.basename(remote_url.rstrip("/")))[0]
        except Exception as e:
            logger.warning(f"Failed to read remote origin: {e}")

        if not repo_name:
            repo_name = os.path.basename(os.path.abspath(self.repo_path))

        try:
            default_branch = self.repo.head.shorthand
        except pygit2.GitError:
            default_branch = None

        description_file = os.path.join(self.repo_path, ".git", "description")
        description = ""
        if os.path.exists(description_file):
            with open(description_file, "r") as f:
                description = f.read().strip()
                if description.startswith("Unnamed repository"):
                    description = "No description available"

        try:
            tree_string = get_tree(self.repo_path)
        except Exception as e:
            logger.warning(f"Failed to build project tree: {e}")
            tree_string = ""

        self.nodes["metadata"] = {
            "name": repo_name,
            "remote_url": remote_url,
            "description": description,
            "default_branch": default_branch,
            "tree": tree_string,
        }
        return self.nodes["metadata"]
    
    def diff_files_between_branches(self, repo: pygit2.Repository, default_branch: str, other_branch: str) -> dict:
        """Compare file changes between default_branch and other_branch."""
        try:
            default_commit = repo.branches.get(default_branch).peel()
            other_commit = repo.branches.get(other_branch).peel()

            def collect_paths(commit):
                paths = set()

                def walk_tree(tree, base=""):
                    for entry in tree:
                        path = os.path.join(base, entry.name)
                        if entry.filemode == pygit2.GIT_FILEMODE_TREE:
                            walk_tree(repo[entry.id], path)
                        else:
                            paths.add(path)
                walk_tree(commit.tree)
                return paths

            paths_default = collect_paths(default_commit)
            paths_other = collect_paths(other_commit)

            added = sorted(paths_other - paths_default)
            removed = sorted(paths_default - paths_other)

            # Modified = intersection
            modified_files = sorted(paths_default & paths_other)

            # Build diff output
            diff = repo.diff(default_commit, other_commit)
            modified = []

            for patch in diff:
                path = patch.delta.new_file.path
                if path in modified_files:
                    lines = []
                    lines.append(f"diff --git a/{patch.delta.old_file.path} b/{patch.delta.new_file.path}")
                    for hunk in patch.hunks:
                        lines.append(hunk.header.strip())
                        for line in hunk.lines:
                            prefix = line.origin  # '+', '-', ' ', etc.
                            content = line.content.rstrip()
                            lines.append(f"{prefix}{content}")
                    modified.append({
                        "file_path": path,
                        "diff": "\n".join(lines)
                    })

            return {
                "added": added,
                "removed": removed,
                "modified": modified
            }

        except Exception as e:
            logger.warning(f"Failed to diff branches '{default_branch}' vs '{other_branch}': {e}")
            return {
                "added": [],
                "removed": [],
                "modified": []
            }


    def get_branches(self):
        branch_dicts = []
        repo_name = self.nodes["metadata"].get("name", "unknown")
        default_branch = self.nodes["metadata"].get("default_branch")

        # print("--"*150)
        print("--"*150)
        
        # logger.info("Listing local branches: %s", list(self.repo.branches.local))
        logger.info("Listing remote branches: %s", list(self.repo.branches.remote))


        for remote_branch in self.repo.branches.remote:
            try:
                branch_ref = self.repo.branches.local.get(remote_branch)
                if not branch_ref:
                    continue

                commit = self.repo[branch_ref.target]

                try:
                    branch_tree_string = self._get_tree_from_commit(branch_ref.target)
                except Exception as e:
                    logger.warning(f"Failed to extract tree for branch '{remote_branch}': {e}")
                    branch_tree_string = ""

                # Count commits
                commit_count = sum(1 for _ in self.repo.walk(commit.id, pygit2.GIT_SORT_TOPOLOGICAL))

                # Diff with default branch (skip if same)
                diff_file = {}
                if default_branch and remote_branch != default_branch:
                    diff_file = self.diff_files_between_branches(self.repo, default_branch, remote_branch)

                branch_dicts.append({
                    "name": remote_branch,
                    "is_head": branch_ref.is_head(),
                    "is_default": remote_branch == default_branch,
                    "is_remote_tracking": True,
                    "upstream_name": None,
                    "remote_name": remote_branch,
                    "latest_commit_id": str(commit.id),
                    "commit_count": commit_count,
                    "repository": repo_name,
                    "tree": branch_tree_string,
                    "file_diff":diff_file,
                })
            except Exception as e:
                logger.warning(f"Failed to process branch '{remote_branch}': {e}")

        self.nodes["branches"] = branch_dicts
        return branch_dicts

    @staticmethod
    def _commit_name(message: str, max_words: int = 10, max_chars: int = 60) -> str:
        first_line = message.strip().split('\n')[0]
        words = first_line.split()
        if len(words) > max_words:
            first_line = " ".join(words[:max_words]) + "..."
        if len(first_line) > max_chars:
            first_line = first_line[:max_chars].rstrip() + "..."
        return first_line

    def collect_all_commits(self):
        commits = []
        visited = set()
        repo_name = self.nodes["metadata"].get("name", "unknown")

        for ref_name in self.repo.references:
            if not ref_name.startswith("refs/heads/"):
                continue

            branch_name = ref_name.split("/")[-1]
            try:
                target = self.repo.lookup_reference(ref_name).target
                for commit in self.repo.walk(target, pygit2.GIT_SORT_TIME):
                    cid = str(commit.id)
                    if cid in visited:
                        continue
                    visited.add(cid)

                    if not commit.parents:
                        continue

                    parent = commit.parents[0]
                    try:
                        diff = self.repo.diff(parent, commit)
                    except Exception as e:
                        logger.warning(f"Diff failed for commit {cid}: {e}")
                        continue

                    touched_files = []
                    for patch in diff:
                        full_path = os.path.normpath(os.path.join(repo_name, patch.delta.new_file.path))
                        lines = []
                        for hunk in patch.hunks:
                            lines.append(hunk.header)
                            lines.extend(f"{line.origin}{line.content.strip()}" for line in hunk.lines)
                        touched_files.append({
                            "file_path": full_path,
                            "diff": "\n".join(lines)
                        })

                    commits.append({
                        "id": cid,
                        "name": self._commit_name(commit.message),
                        "message": commit.message.strip(),
                        "author": commit.author.name,
                        "email": commit.author.email,
                        "timestamp": commit.commit_time,
                        "parents": [str(p.id) for p in commit.parents],
                        "branch": branch_name,
                        "repository": repo_name,
                        "touched_files": touched_files,
                    })
            except Exception as e:
                logger.warning(f"Failed to process branch {branch_name}: {e}")

        self.nodes["commits"] = commits
        return commits

    def get_tree_dicts(self, commit):
        tree = commit.tree
        repo_name = self.nodes["metadata"]["name"]
        base_path = self.repo.workdir or repo_name
        folders = []
        files = []

        def walk(tree, parent_full_path):
            for entry in tree:
                full_path = os.path.join(parent_full_path, entry.name)
                relative_path = os.path.relpath(full_path, base_path)
                path = os.path.normpath(os.path.join(repo_name, relative_path))

                relative_parent = os.path.relpath(parent_full_path, base_path)
                parent_path = repo_name if relative_parent in (".", "") else os.path.normpath(os.path.join(repo_name, relative_parent))

                try:
                    folder_tree = get_tree(full_path)
                except Exception as e:
                    logger.warning(f"Failed to get tree for folder {full_path}: {e}")
                    folder_tree = ""

                if entry.filemode == pygit2.GIT_FILEMODE_TREE:
                    folders.append({
                        "type": "folder",
                        "name": entry.name,
                        "path": path,
                        "parent_path": parent_path,
                        "repository": repo_name,
                        "tree": folder_tree
                    })
                    walk(self.repo[entry.id], full_path)
                else:
                    _, ext = os.path.splitext(entry.name)
                    files.append({
                        "type": "file",
                        "name": entry.name,
                        "path": path,
                        "extension": ext.lstrip("."),
                        "parent_path": parent_path,
                        "repository": repo_name
                    })

        walk(tree, base_path)
        return folders, files
