"""The scope map's recorder (the testing plan of 19 November 2026, item E, §10.5; D229 rule 3, D358).
Gate tooling, not part of the engine; nothing here changes what a process computes.

Python's site machinery imports this module as sitecustomize when scripts/gates/scope_inject is on
PYTHONPATH, which scripts/test_tiers.py arranges only for `run --scope-map`. It first runs the
sitecustomize it shadows. Then, only when CELLS_SCOPE_LOG and CELLS_SCOPE_ROOT are set, it records
what the process touches of the repository at CELLS_SCOPE_ROOT, one JSON line per new fact, appended
to a file of its own under CELLS_SCOPE_LOG as it happens (so a process killed at its cap keeps what
it saw). The class of the code that asked goes with each fact: the import system, pytest, or other
code (its repository file, a library, or the standard library); a pytest session that the
repository's own code starts is that code's.
  open    a file opened, by name or relative to a descriptor (dir_fd);
  stat    a path whose existence, kind, size or mode was asked (os.stat, os.lstat, os.access,
          os.readlink, os.chdir), present or not; of pytest's own, only the names that change how it
          runs a file (conftest, package and configuration files), not its scan of each entry for a
          virtual environment;
  list    a folder listed (os.listdir and os.scandir, so glob, os.walk and pathlib's globs too), by
          each class that lists it. "via" names the standard library's own discovery when the
          listing (or the question) went through it: pkgutil or importlib.metadata. "entries" marks
          a scandir by the repository's own code, which then holds the entries' sizes and modes;
  link    a link made to a path of the repository, through which anything may be read unseen;
  root    a folder on sys.path, and top: a top-level name looked up by an import there;
  sub     a name looked up in a package of the repository;
  child   a child started (_posixsubprocess.fork_exec, which subprocess and multiprocessing use, or
          os.posix_spawn), with its process number, its arguments and its folder; a repository path
          among the arguments is a read. os.system has no number, and exec replaces this process;
  process this process, its parent, its arguments, the repository, and whether it was forked.
At exit it adds the repository's modules in sys.modules. A Python child records itself: it inherits
the variables and PYTHONPATH, and a child whose environment was rebuilt or replaced is given them at
the exec boundary, unless it carries another recorder's. One that does not record itself (another
program, python -I) is a child without a record, for scope.py to account for.
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
    import _posixsubprocess
    import atexit
    import json
    import threading

    inject = os.path.dirname(os.path.abspath(__file__))
    own = _start.__code__.co_filename
    stdlib = os.path.dirname(os.__file__) + os.sep
    discovery = {stdlib + "pkgutil.py": "pkgutil",
                 os.path.join(stdlib, "importlib", "metadata", "__init__.py"): "metadata"}
    root = os.path.realpath(root)
    prefix = root + os.sep
    local = threading.local()
    state = {"handle": None, "seen": set(), "lock": threading.RLock(), "path": None}
    real = {name: getattr(os, name) for name in ("stat", "lstat", "access", "readlink", "open")}
    pytest_names = frozenset(("conftest.py", "__init__.py", "pytest.toml", ".pytest.toml", "pytest.ini",
                              ".pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg"))
    events = frozenset(("open", "os.listdir", "os.scandir", "os.chdir", "os.symlink", "os.link", "import",
                        "os.system", "os.exec"))

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
        if not os.path.isabs(path):
            path = os.path.join(cwd or os.getcwd(), path)
        full = os.path.normpath(path)
        if full == root:
            return "."
        return full[len(prefix):] if full.startswith(prefix) else None

    def held(descriptor):
        """The path a descriptor holds (None when it holds none)."""
        try:
            return real["readlink"](f"/proc/self/fd/{descriptor}")
        except OSError:
            return None

    def write(row, key=None):
        if key is not None:
            if key in state["seen"]:
                return
            state["seen"].add(key)
        with state["lock"]:
            state["handle"].write(json.dumps(row) + "\n")

    def fault(what):  # A recorder fault must never change the run; the file shows the gap.
        write({"fault": f"{what}: {sys.exc_info()[0].__name__}"})

    def open_log(forked):
        local.busy = True
        state["lock"] = threading.RLock()  # A fork's child must not inherit a lock some thread held.
        try:
            os.makedirs(log_dir, exist_ok=True)
            name = f"{os.getpid()}-{os.urandom(4).hex()}.jsonl"
            state["handle"] = open(os.path.join(log_dir, name), "a", buffering=1, encoding="utf-8")
            state["seen"], state["path"] = set(), None
            write({"process": os.getpid(), "parent": os.getppid(), "forked": forked, "root": root,
                   "argv": [str(a) for a in getattr(sys, "orig_argv", sys.argv)]})
        finally:
            local.busy = False

    def caller():
        """(class, via, direct): the class of the code that asked (import, pytest, repo:PATH, library
        or stdlib), the standard library's discovery it asked through, and whether the repository's
        code made the call itself."""
        frame = sys._getframe(1)
        while frame is not None and frame.f_code.co_filename == own:
            frame = frame.f_back
        if frame is None:  # Asked from C with no Python caller (a thread's start, shutdown).
            return "stdlib", None, False
        first, via = frame, None
        if frame.f_code.co_filename.startswith("<frozen importlib"):
            return "import", None, False
        while frame is not None:
            name = frame.f_code.co_filename
            if not name.startswith((stdlib, "<")) or "site-packages" in name:
                break
            via = discovery.get(name, via)
            frame = frame.f_back
        if frame is None:
            return "stdlib", via, False
        name = frame.f_code.co_filename
        if "/_pytest/" in name or "/pluggy/" in name or "/pytest/" in name:
            outer = frame.f_back
            while outer is not None:  # A session the repository's code started (pytest.main)?
                inner = outer.f_code.co_filename
                if inner.startswith(prefix) and inner != own:
                    return f"repo:{inner[len(prefix):]}", via, False
                outer = outer.f_back
            return "pytest", via, False
        where = rel(name)
        return (f"repo:{where}" if where else "library"), via, bool(where) and frame is first

    def searched():
        """The repository's folders on sys.path, noted whenever it (or the current folder) changes."""
        try:
            here = os.getcwd()
        except OSError:  # It was removed: the empty entry of sys.path then finds nothing.
            here = None
        now = (tuple(str(e) for e in sys.path), here)
        if now != state["path"]:
            state["path"] = now
            for entry in now[0]:
                where = rel(entry or os.curdir, here) if here or os.path.isabs(entry) else None
                if where:
                    write({"root": where}, ("root", where))

    def hook(event, args):
        if event not in events or getattr(local, "busy", False) or state["handle"] is None:
            return
        local.busy = True
        try:
            if event == "open":
                where = None if isinstance(args[0], int) else rel(args[0], getattr(local, "folder", None))
                if where:
                    who = caller()[0]
                    write({"open": where, "by": who}, ("open", where, who))
            elif event in ("os.listdir", "os.scandir"):
                target = args[0] if args and args[0] not in (None, "", b"") else os.curdir
                where = rel(held(target) if isinstance(target, int) else target)
                if where:
                    who, via, direct = caller()
                    row = {"list": where, "by": who}
                    if via:
                        row["via"] = via
                    if direct and event == "os.scandir":
                        row["entries"] = True
                    write(row, ("list", where, who, via, "entries" in row))
            elif event == "os.chdir":
                where = None if isinstance(args[0], int) else rel(args[0])
                asked(where, caller())
            elif event in ("os.symlink", "os.link"):  # What is read through it carries no path of the tree.
                made = os.path.abspath(os.fsdecode(args[1])) if event == "os.symlink" else ""
                where = rel(args[0], os.path.dirname(made))
                if where:
                    write({"link": where}, ("link", where))
            elif event == "import":
                if "." not in args[0]:
                    write({"top": args[0]}, ("top", args[0]))
            elif event == "os.exec":
                write({"exec": [os.fsdecode(a) for a in args[1]], "cwd": os.getcwd(),
                       **programs([args[0]], os.getcwd()), "git": git(os.environb)})
            elif event == "os.system":
                write({"child": None, "argv": ["sh", "-c", os.fsdecode(args[0])], "cwd": os.getcwd()})
        except Exception:
            fault(event)
        finally:
            local.busy = False

    def asked(where, by):
        """One question about a path: its existence, kind, size or mode."""
        who, via, _ = by
        if where and (who != "pytest" or os.path.basename(where) in pytest_names):
            row = {"stat": where, "by": who, **({"via": via} if via else {})}
            write(row, ("stat", where, who, via))

    def question(function):
        def wrapper(path, *args, **kwargs):
            if (not getattr(local, "busy", False) and state["handle"] is not None
                    and not isinstance(path, int)):
                local.busy = True
                try:
                    folder = kwargs.get("dir_fd")
                    where = rel(path, None if folder is None else held(folder))
                    if where:
                        asked(where, caller())
                except Exception:
                    fault(function.__name__)
                finally:
                    local.busy = False
            return function(path, *args, **kwargs)
        wrapper.__name__, wrapper.__doc__ = function.__name__, function.__doc__
        return wrapper

    def opener(function):
        def wrapper(path, flags, mode=0o777, *, dir_fd=None):
            # The audit event names the path alone: the hook reads it against this folder.
            before = getattr(local, "folder", None)
            local.folder = None if dir_fd is None else held(dir_fd)
            try:
                return function(path, flags, mode, dir_fd=dir_fd)
            finally:
                local.folder = before
        wrapper.__name__, wrapper.__doc__ = function.__name__, function.__doc__
        return wrapper

    # ---------------------------------------------------------------------------- imports

    class Seeker:
        """First on sys.meta_path, and finds nothing: it notes each name an import looks up in the
        repository, so a new file that another lookup would find first (or at all) is seen."""

        @classmethod
        def find_spec(cls, name, path=None, target=None):
            if not getattr(local, "busy", False) and state["handle"] is not None:
                local.busy = True
                try:
                    if path is None:
                        searched()
                        write({"top": name}, ("top", name))
                    else:
                        leaf = name.rpartition(".")[2]
                        for entry in list(path):
                            where = rel(entry)
                            if where:
                                write({"sub": where, "name": leaf}, ("sub", where, leaf))
                except Exception:
                    fault("find_spec")
                finally:
                    local.busy = False
            return None

    # --------------------------------------------------------------------------- children

    mine = {b"CELLS_SCOPE_LOG": os.fsencode(log_dir), b"CELLS_SCOPE_ROOT": os.fsencode(root)}

    def carrying(env):
        """A child's environment (a list of K=V bytes) with this recorder in it: the same list when
        it is there already, or when the environment carries another recorder's."""
        have = dict(item.partition(b"=")[::2] for item in env)
        log = have.get(b"CELLS_SCOPE_LOG")
        python = have.get(b"PYTHONPATH", b"")
        inside = os.fsencode(inject) in python.split(os.fsencode(os.pathsep))
        if log not in (None, mine[b"CELLS_SCOPE_LOG"]):
            return env
        if inside and all(have.get(k) == v for k, v in mine.items()):
            return env
        if not inside:
            python = os.fsencode(inject) + (os.fsencode(os.pathsep) + python if python else b"")
        kept = [i for i in env if i.partition(b"=")[0] not in (*mine, b"PYTHONPATH")]
        return kept + [k + b"=" + v for k, v in mine.items()] + [b"PYTHONPATH=" + python]

    def current():
        return [k + b"=" + v for k, v in os.environb.items()]

    def git(env):
        """Whether a git variable names the repository (git would then read it wherever it runs)."""
        items = env.items() if hasattr(env, "items") else (i.partition(b"=")[::2] for i in env)
        return any(k.startswith(b"GIT_") and os.fsencode(root) in v for k, v in items)

    def programs(candidates, folder):
        """Where a child's program is found, and whether it is nowhere (then no child runs). A
        candidate in the repository is a path among the child's arguments, there or not."""
        there = []
        for path in [os.path.normpath(os.path.join(folder, os.fsdecode(c))) for c in candidates]:
            argument(path, folder)
            try:
                real["stat"](path)
                there.append(path)
            except OSError:
                pass
        return {"program": there[0] if there else None}

    def argument(arg, folder):
        where = rel(arg, folder) if os.sep in arg else None
        if where:
            write({"arg": where}, ("arg", where))

    def child(pid, argv, found, folder, env):
        argv = [os.fsdecode(a) for a in argv]
        write({"child": pid, "argv": argv, "cwd": folder, **found, "git": git(env)})
        for arg in argv:
            argument(arg, folder)

    real_fork_exec = _posixsubprocess.fork_exec

    def fork_exec(args, executable_list, close_fds, pass_fds, cwd, env, *rest):
        note = not getattr(local, "busy", False) and state["handle"] is not None
        if note:
            local.busy = True
            try:
                given = current() if env is None else list(env)
                now = carrying(given)
                if now is not given:
                    env = now
                folder = os.path.join(os.getcwd(), os.fsdecode(cwd)) if cwd is not None else os.getcwd()
                found = programs(executable_list, folder)
            except Exception:
                note = False
                fault("fork_exec")
            finally:
                local.busy = False
        pid = real_fork_exec(args, executable_list, close_fds, pass_fds, cwd, env, *rest)
        if note:
            local.busy = True
            try:
                child(pid, args, found, folder, now)
            except Exception:
                fault("fork_exec")
            finally:
                local.busy = False
        return pid

    def spawner(function):
        def wrapper(path, argv, env, /, **kwargs):
            note = not getattr(local, "busy", False) and state["handle"] is not None
            if note:
                local.busy = True
                try:
                    given = current() if env is None else [
                        os.fsencode(k) + b"=" + os.fsencode(v) for k, v in env.items()]
                    now = carrying(given)
                    if now is not given:
                        env = dict(item.partition(b"=")[::2] for item in now)
                    folder = os.getcwd()
                    found = programs([path], folder)
                except Exception:
                    note = False
                    fault(function.__name__)
                finally:
                    local.busy = False
            pid = function(path, argv, env, **kwargs)
            if note:
                local.busy = True
                try:
                    child(pid, argv, found, folder, now)
                except Exception:
                    fault(function.__name__)
                finally:
                    local.busy = False
            return pid
        wrapper.__name__, wrapper.__doc__ = function.__name__, function.__doc__
        return wrapper

    # ------------------------------------------------------------------------------- exit

    def at_exit():
        local.busy = True
        try:
            searched()
            files = set()
            for name, module in list(sys.modules.items()):
                write({"top": name.partition(".")[0]}, ("top", name.partition(".")[0]))
                where = rel(getattr(module, "__file__", None) or "")
                if where:
                    files.add(where)
            write({"exit": True, "modules": sorted(files)})
            state["handle"].flush()
        except Exception:
            fault("exit")  # This thread stays busy: what a finalizer opens now, the trace shows.

    open_log(False)
    searched()
    os.register_at_fork(after_in_child=lambda: open_log(True))
    for name, wrap in (("stat", question), ("lstat", question), ("access", question),
                       ("readlink", question), ("open", opener)):
        original = real[name]
        wrapper = wrap(original)
        setattr(os, name, wrapper)
        # os.supports_* hold the functions themselves; code that tests membership (shutil picks its
        # descriptor-based rmtree so, at import) must see the wrapper as it saw the original.
        for group in (os.supports_fd, os.supports_dir_fd, os.supports_follow_symlinks,
                      os.supports_effective_ids):
            if original in group:
                group.add(wrapper)
    os.posix_spawn, os.posix_spawnp = spawner(os.posix_spawn), spawner(os.posix_spawnp)
    _posixsubprocess.fork_exec = fork_exec
    if "subprocess" in sys.modules:  # It binds the function by name when it is imported.
        sys.modules["subprocess"]._fork_exec = fork_exec
    sys.meta_path.insert(0, Seeker)
    sys.addaudithook(hook)
    atexit.register(at_exit)


if os.environ.get("CELLS_SCOPE_LOG") and os.environ.get("CELLS_SCOPE_ROOT"):
    _start(os.environ["CELLS_SCOPE_ROOT"], os.environ["CELLS_SCOPE_LOG"])
