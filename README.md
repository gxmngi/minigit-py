# minigit-py

[![CI](https://github.com/gxmngi/minigit-py/actions/workflows/ci.yml/badge.svg)](https://github.com/gxmngi/minigit-py/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> *"What I cannot create, I do not understand."* — Richard Feynman

A lightweight Git implementation written from scratch in Python. Built to deeply understand Git internals, content-addressable storage, directed acyclic graphs (DAG), and the object database behind version control.

Part of the **[Build Your Own X](https://github.com/codecrafters-io/build-your-own-x)** challenge.

---

## 🧠 Git Internals & Architecture

Linus Torvalds famously designed Git not as a Version Control System, but as a **content-addressable filesystem** with a VCS user interface layered on top.

```
.git/
├── HEAD               # Points to active branch ref (e.g. ref: refs/heads/main)
├── config             # INI repository configuration (repositoryformatversion, filemode)
├── description        # Human-readable repository description
├── objects/           # Content-addressable object store ([type] [size]\0[content] -> SHA-1)
└── refs/
    ├── heads/         # Local branch pointers (files containing 40-hex commit SHA-1)
    └── tags/          # Annotated and lightweight tag pointers
```

---

## 🚀 Quickstart

### Installation (Editable Mode)

```bash
git clone https://github.com/gxmngi/minigit-py.git
cd minigit-py
pip install -e .
```

### Usage

Initialize a new repository:

```bash
# Initialize inside a target folder
minigit init my-new-project

# Or initialize inside current directory
minigit init
```

---

## 🗺️ Roadmap & Milestones

- [x] **Milestone 1: Repository Architecture & Init**
  - `.git` directory creation hierarchy
  - `HEAD`, `config`, and `refs` management
  - Upward repository discovery (`repo_find`)
- [ ] **Milestone 2: Object Model & Storage**
  - Raw Git Object serialization (`[type] [size]\x00[content]`)
  - SHA-1 content hashing & `zlib` compression
  - `minigit hash-object` (write object to `.git/objects/`)
  - `minigit cat-file` (read and decompress object)
- [ ] **Milestone 3: Trees & Commits**
  - Tree parsing & leaf entry creation
  - Commit object assembly (tree pointer, parent, author, committer, timestamp, message)
  - `minigit commit-tree` / `minigit log`
- [ ] **Milestone 4: Staging Area & Working Tree**
  - Git Index (`.git/index`) binary parser
  - `minigit add`
  - `minigit status`

---

## 🧪 Testing

Run the automated test suite with pytest:

```bash
pytest -v
```

---

## 📜 License

Distributed under the [MIT License](LICENSE). Built with curiosity by [Rusdan Lamsa (@gxmngi)](https://github.com/gxmngi).
