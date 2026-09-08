# MiniGit

<p align="left">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" /></a>
  <a href="https://github.com/gxmngi/minigit-py/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/gxmngi/minigit-py/ci.yml?branch=main&style=flat-square&logo=githubactions&logoColor=white" alt="CI" /></a>
  <img src="https://img.shields.io/badge/Internals-Blobs_%2F_Trees_%2F_Commits-orange?style=flat-square" alt="Git Internals" />
  <img src="https://img.shields.io/badge/Hashing-SHA--1-blueviolet?style=flat-square" alt="SHA-1" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-gray?style=flat-square" alt="License" /></a>
</p>

> "What I cannot create, I do not understand." — Richard Feynman

A lightweight Git implementation written from scratch in Python. Designed to explore Git internals, content-addressable storage, object hashing, recursive directory trees, directed acyclic commit graphs, and working tree restoration.

Part of the [Build Your Own X](https://github.com/codecrafters-io/build-your-own-x) challenge. Fully binary-compatible with official Git.

---

## Git Internals and Architecture

Git operates as a content-addressable filesystem with a version control user interface layered on top:

```
.git/
├── HEAD               # Symbolic pointer to current branch (e.g. ref: refs/heads/main)
├── config             # INI repository configuration (repositoryformatversion, filemode)
├── description        # Human-readable repository description
├── objects/           # Content-addressable object store ([type] [size]\x00[payload] -> SHA-1)
│   └── 3b/
│       └── 18e512...  # Compressed with zlib into 256-directory fan-out hierarchy
└── refs/
    ├── heads/         # Branch pointers (files containing 40-character commit SHA-1)
    └── tags/          # Annotated and lightweight tag pointers
```

### Object Model

Every Git object shares a universal serialized header before compression:

```
b"[type] [size]\x00[content]"
```

- **Blob**: Pure file content (stores raw bytes, omitting filename and permissions).
- **Tree**: Directory snapshot containing a list of `[mode] [path]\x00[20-byte-binary-sha]`.
- **Commit**: Links a root tree snapshot, parent commit SHA(s), author/committer timestamps, and commit message.

---

## Quickstart

### Installation

Clone and install in editable mode:

```bash
git clone https://github.com/gxmngi/minigit-py.git
cd minigit-py
pip install -e .
```

---

## CLI Command Reference

### Repository Initialization

```bash
# Initialize repository in current directory
minigit init

# Initialize repository in specific path
minigit init my-repo
```

### Object Database Operations

```bash
# Compute SHA-1 hash for a file
minigit hash-object file.txt

# Compute SHA-1 and write zlib-compressed object to .git/objects/
minigit hash-object -w file.txt

# View object content (pretty-print)
minigit cat-file -p <object-sha>

# View object type (blob, tree, commit)
minigit cat-file -t <object-sha>

# View object raw size in bytes
minigit cat-file -s <object-sha>
```

### Tree and Directory Management

```bash
# Scan directory recursively and write root tree object
minigit write-tree

# List contents of a tree object
minigit ls-tree <tree-sha>

# Recursively list all files in a tree
minigit ls-tree -r <tree-sha>

# List file names only
minigit ls-tree --name-only <tree-sha>
```

### Commit Graphs and History

```bash
# Create a commit from an existing tree
minigit commit-tree <tree-sha> -m "Initial commit"

# Create a child commit pointing to parent commit
minigit commit-tree <tree-sha> -p <parent-commit-sha> -m "Next commit"

# Traverse commit graph and view history log
minigit log
minigit log <commit-sha>
```

### Branches and Working Tree Checkout

```bash
# List existing branches (* denotes active branch)
minigit branch

# Create a new branch pointing to current HEAD
minigit branch feature-branch

# Update a reference pointer manually
minigit update-ref refs/heads/main <commit-sha>

# Switch branch and restore working tree files from snapshot
minigit checkout feature-branch

# Create and switch to new branch in one step
minigit checkout -b experiment
```

### Three-Way Merge and Conflict Resolution

```bash
# Find Lowest Common Ancestor (merge-base) between two commits
minigit merge-base <commit1> <commit2>

# Fast-forward or three-way merge target branch into current branch
minigit merge feature-branch

# Custom merge commit message
minigit merge feature-branch -m "Merge feature-branch into main"
```

---

## Roadmap and Completed Milestones

- [x] **Milestone 1: Repository Architecture and Discovery**
  - Directory hierarchy: `.git`, `objects/`, `refs/heads/`, `refs/tags/`
  - Upward parent search (`repo_find`) with ceiling directory guard
  - Standard INI configuration parsing

- [x] **Milestone 2: Content-Addressable Object Database**
  - Universal header serialization (`b"[type] [size]\x00[content]"`)
  - SHA-1 content hashing with byte-level parity to official Git
  - Object storage with 2/38 fan-out directory structure and `zlib` compression
  - Inspection commands: `hash-object -w`, `cat-file -p/-t/-s`

- [x] **Milestone 3: Directory Trees and Recursive Structure**
  - Binary 20-byte SHA-1 tree leaf serialization
  - Canonical directory mode formatting (`40000` / `100644`) matching Git C core
  - Recursive working directory scanning (`write-tree`)
  - Tree listing commands (`ls-tree -r`, `--name-only`)

- [x] **Milestone 4: Commit Graphs and History Traversal**
  - Commit object serialization with tree pointer, parents, and author timestamps
  - Timezone and author parsing
  - Graph traversal along parent ancestry (`log`)

- [x] **Milestone 5: References, Branches, and Working Tree Checkout**
  - Symbolic reference resolution (`.git/HEAD`)
  - Branch creation and listing in O(1) time
  - Working tree snapshot restoration (`checkout [-b]`)

- [x] **Milestone 6: Three-Way Merge Engine and Conflict Marker Synthesis**
  - Lowest Common Ancestor (LCA) DAG search (`merge-base`)
  - Fast-forward detection and branch advancing
  - Three-way tree snapshot diff and line-level merge
  - Conflict marker synthesis (`<<<<<<< HEAD`, `=======`, `>>>>>>>`) on overlapping edits
  - Automated merge commit creation with dual parent pointers

---

## Testing and Verification

All features are verified against official Git behavior with an automated test suite:

```bash
pytest -v
```

Cross-compatibility tests run real `git` commands alongside `minigit` to verify 100% hash and tree structure parity.

---

## License

Distributed under the [MIT License](LICENSE). Maintained by [Rusdan Lamsa (@gxmngi)](https://github.com/gxmngi).
