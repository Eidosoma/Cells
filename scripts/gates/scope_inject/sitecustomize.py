"""The scope map's recorder (the testing plan of 19 November 2026, item E, §10.5; D229 rule 3).
Gate tooling, not part of the engine; nothing here changes what a process computes.

Python's site machinery imports this module as sitecustomize when scripts/gates/scope_inject is on
PYTHONPATH, which scripts/test_tiers.py arranges only for `run --scope-map`. It first runs the
sitecustomize it shadows. Then, only when CELLS_SCOPE_LOG and CELLS_SCOPE_ROOT are set, it records
what the process touches of the repository at CELLS_SCOPE_ROOT, one JSON line per new fact, appended
to a file of its own under CELLS_SCOPE_LOG as it happens (so a process killed at its cap keeps what
it saw):
  open    a file opened, with the caller's class: the import system, pytest, or other code (its
          repository file, a library, or the standard library);
  stat    a path whose existence or kind was asked (os.stat, os.lstat, os.access), present or not;
          of pytest's own, only the names that change how it runs a file (PYTEST_NAMES: conftest,
          package and configuration files), not its scan of each entry for a virtual environment;
  list    a directory listed (os.listdir and os.scandir, so glob, os.walk and pathlib's globs too),
          except the import system's and pytest's own listings (pytest collects only the file it
          is given; a new conftest or package file shows through its stat);
  spawn   a child started (subprocess, os.posix_spawn, os.system), with its arguments and whether
          its environment carries this recorder; a repository path among the arguments is a read;
  process this process, its parent, its arguments, and whether it was forked.
At exit it adds the repository's modules in sys.modules, the files that would have satisfied each
failed import, and the files that would shadow each top-level repository module on sys.path. A
Python child inherits the two variables and PYTHONPATH, so it records itself; one that does not
(another program, or a cleared environment) shows as a spawn without a child's record.
"""

import os
import sys


def _chain():
    """Run the sitecustomize this module shadows (the next one on sys.path), as Python would."""
    here = os.path.dirname(os.path.abspath(__file__))
    for entry in sys.path:
        folder = os.path.abspath(entry or os.curdir)
        path = os.path.join(folder, "sitecustomize.py")
        if folder != here and os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                code = compile(handle.read(), path, "exec")
            exec(code, {"__name__": "sitecustomize", "__file__": path})
            return


_chain()


def _start(root, log_dir):
    import atexit
    import json
    import threading

    inject = os.path.dirname(os.path.abspath(__file__))
    stdlib = os.path.dirname(os.__file__) + os.sep
    root = os.path.realpath(root)
    prefix = root + os.sep
    local = threading.local()
    state = {"handle": None, "seen": set(), "imports": set(), "lock": threading.RLock()}
    pytest_names = frozenset(("conftest.py", "__init__.py", "pytest.ini", ".pytest.ini", "pyproject.toml",
                              "tox.ini", "setup.cfg"))
    events = frozenset(("open", "os.listdir", "os.scandir", "import", "subprocess.Popen",
                        "os.posix_spawn", "os.system"))

    def rel(path, cwd=None):
        """The repository-relative path, or None for a path outside it (or a descriptor)."""
        try:
            path = os.fspath(path)
        except TypeError:
            return None
        if isinstance(path, bytes):
            path = os.fsdecode(path)
        if not isinstance(path, str) or not path:
            return None
        full = os.path.normpath(os.path.join(cwd or os.getcwd(), path))
        if full == root:
            return "."
        return full[len(prefix):] if full.startswith(prefix) else None

    def write(row, key=None):
        if key is not None:
            if key in state["seen"]:
                return
            state["seen"].add(key)
        with state["lock"]:
            state["handle"].write(json.dumps(row) + "\n")

    def open_log(forked):
        local.busy = True
        state["lock"] = threading.RLock()  # A fork's child must not inherit a lock some thread held.
        try:
            os.makedirs(log_dir, exist_ok=True)
            name = f"{os.getpid()}-{os.urandom(4).hex()}.jsonl"
            state["handle"] = open(os.path.join(log_dir, name), "a", buffering=1, encoding="utf-8")
            state["seen"] = set()
            write({"process": os.getpid(), "parent": os.getppid(), "forked": forked,
                   "argv": [str(a) for a in getattr(sys, "orig_argv", sys.argv)]})
        finally:
            local.busy = False

    def caller(depth=2):
        """The class of the code that asked: import, pytest, repo:PATH, library or stdlib."""
        try:
            frame = sys._getframe(depth)
        except ValueError:  # Asked from C with no Python caller (a thread's start, shutdown).
            return "stdlib"
        if frame.f_code.co_filename.startswith("<frozen importlib"):
            return "import"
        while frame is not None:
            name = frame.f_code.co_filename
            if not (name.startswith(stdlib) or name.startswith("<")) or "site-packages" in name:
                break
            frame = frame.f_back
        if frame is None:
            return "stdlib"
        name = frame.f_code.co_filename
        if "/_pytest/" in name or "/pluggy/" in name or "/pytest/" in name:
            return "pytest"
        where = rel(name)
        return f"repo:{where}" if where else "library"

    def spawned(argv, cwd, env, kind):
        argv = [os.fsdecode(a) if isinstance(a, bytes) else str(a) for a in argv]
        if env is None:
            inherits = True
        else:
            get = lambda k: env.get(k) or env.get(k.encode(), b"").decode()  # noqa: E731
            inherits = bool(get("CELLS_SCOPE_LOG")) and inject in str(get("PYTHONPATH")).split(os.pathsep)
        write({"spawn": argv, "kind": kind, "inherits": inherits})
        for arg in argv:
            where = rel(arg, os.fspath(cwd) if cwd else None) if "/" in arg or os.sep in arg else None
            if where:
                write({"arg": where}, ("arg", where))

    def hook(event, args):
        if event not in events or getattr(local, "busy", False) or state["handle"] is None:
            return
        local.busy = True
        try:
            if event == "open":
                where = rel(args[0]) if not isinstance(args[0], int) else None
                if where:
                    who = caller()
                    write({"open": where, "by": who}, ("open", where, who))
            elif event in ("os.listdir", "os.scandir"):
                target = args[0] if args and args[0] not in (None, "", b"") else os.curdir
                where = rel(target) if not isinstance(target, int) else None
                who = caller() if where else "import"
                if who not in ("import", "pytest"):
                    write({"list": where, "by": who}, ("list", where))
            elif event == "import":
                state["imports"].add(args[0])
            elif event == "subprocess.Popen":
                spawned(args[1] if isinstance(args[1], (list, tuple)) else [args[1]], args[2], args[3],
                        "popen")
            elif event == "os.posix_spawn" and not sys._getframe(1).f_code.co_filename.endswith(
                    "subprocess.py"):
                spawned(args[1], None, args[2], "posix_spawn")
            elif event == "os.system":
                spawned(["sh", "-c", os.fsdecode(args[0]) if isinstance(args[0], bytes) else args[0]],
                        None, None, "system")
        except Exception:  # A recorder fault must never change the run; the file shows the gap.
            write({"fault": f"{event}: {sys.exc_info()[0].__name__}"})
        finally:
            local.busy = False

    def asked(function):
        def wrapper(path, *args, **kwargs):
            if (not getattr(local, "busy", False) and state["handle"] is not None
                    and not isinstance(path, int) and kwargs.get("dir_fd") is None):
                local.busy = True
                try:
                    where = rel(path)
                    if where:
                        who = caller()
                        if who != "pytest" or os.path.basename(where) in pytest_names:
                            write({"stat": where, "by": who}, ("stat", where, who))
                except Exception:
                    write({"fault": f"{function.__name__}: {sys.exc_info()[0].__name__}"})
                finally:
                    local.busy = False
            return function(path, *args, **kwargs)
        wrapper.__name__, wrapper.__doc__ = function.__name__, function.__doc__
        return wrapper

    def at_exit():
        local.busy = True
        try:
            modules, files = {}, set()
            missing = set()
            entries = [os.path.abspath(e or os.curdir) for e in sys.path]
            for name, module in list(sys.modules.items()):
                where = rel(getattr(module, "__file__", None) or "")
                if where:
                    modules[name] = where
                    files.add(where)
                elif any(rel(str(p)) for p in (getattr(module, "__path__", None) or [])):
                    # A namespace package in the repository: a module or a regular package of its
                    # name anywhere on its search path would take its place.
                    parent, _, leaf = name.rpartition(".")
                    folders = (list(getattr(sys.modules.get(parent), "__path__", None) or [])
                               if parent else entries)
                    for folder in folders:
                        for tail in (leaf + ".py", os.path.join(leaf, "__init__.py")):
                            hit = rel(os.path.join(str(folder), tail))
                            if hit:
                                missing.add(hit)
            for name in state["imports"]:
                if name in sys.modules:
                    continue
                parent, _, leaf = name.rpartition(".")
                if parent:
                    folders = [p for p in getattr(sys.modules.get(parent), "__path__", None) or []]
                else:
                    folders = entries
                for folder in folders:
                    for tail in (leaf + ".py", os.path.join(leaf, "__init__.py"), leaf):
                        where = rel(os.path.join(folder, tail))
                        if where:
                            missing.add(where)
            for name, where in modules.items():  # A file earlier on sys.path would shadow it.
                if "." in name:
                    continue
                home = os.path.join(root, where)
                for folder in entries:
                    if home in (os.path.join(folder, name + ".py"), os.path.join(folder, name, "__init__.py")):
                        break
                    for tail in (name + ".py", os.path.join(name, "__init__.py"), name):
                        hit = rel(os.path.join(folder, tail))
                        if hit:
                            missing.add(hit)
            write({"exit": True, "modules": sorted(files), "absent": sorted(missing)})
            state["handle"].flush()
        except Exception:
            write({"fault": f"exit: {sys.exc_info()[0].__name__}"})

    open_log(False)
    os.register_at_fork(after_in_child=lambda: open_log(True))
    for name in ("stat", "lstat", "access"):
        original = getattr(os, name)
        wrapper = asked(original)
        setattr(os, name, wrapper)
        # os.supports_* hold the functions themselves; code that tests membership (shutil picks its
        # descriptor-based rmtree so, at import) must see the wrapper as it saw the original.
        for group in (os.supports_fd, os.supports_dir_fd, os.supports_follow_symlinks,
                      os.supports_effective_ids):
            if original in group:
                group.add(wrapper)
    sys.addaudithook(hook)
    atexit.register(at_exit)


if os.environ.get("CELLS_SCOPE_LOG") and os.environ.get("CELLS_SCOPE_ROOT"):
    _start(os.environ["CELLS_SCOPE_ROOT"], os.environ["CELLS_SCOPE_LOG"])
