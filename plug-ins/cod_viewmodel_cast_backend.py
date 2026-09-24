"""One project-owned CAST backend shared by all Maya toolkit entry points.

The upstream importer is loaded as a private package, never through Maya's
``castplugin`` registration or the public ``cast`` Python module.  Registering
the translator does not initialize the upstream menu or read/write cast.cfg.
All Maya API use, including this backend, belongs on Maya's main thread.
"""

from contextlib import contextmanager
import hashlib
import importlib.util
import os
import sys
import types


_PACKAGE = "_cod_viewmodel_cast"
_TRANSLATOR = "CoDToolkitCast"


def _identity(path):
    return os.path.normcase(os.path.realpath(path))


def _source_directory(toolkit_plugin_path):
    path = os.fspath(toolkit_plugin_path)
    if not os.path.isabs(path):
        raise ValueError("The toolkit plugin path must be absolute: %s" % path)
    directory = os.path.dirname(os.path.realpath(path))
    candidates = (
        os.path.join(directory, "cod_viewmodel_cast"),
        os.path.join(os.path.dirname(directory), "third_party", "cast"),
    )
    for candidate in candidates:
        if all(os.path.isfile(os.path.join(candidate, name))
               for name in ("cast.py", "castplugin.py")):
            return os.path.realpath(candidate)
    raise RuntimeError(
        "The toolkit's private CAST backend is missing. Reinstall the complete "
        "toolkit package beside %s; an external Cast plugin is not a fallback."
        % path)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load the private CAST module: %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    with open(path, "rb") as source:
        return hashlib.sha256(source.read()).hexdigest()


class _Backend:
    translator_name = _TRANSLATOR

    def __init__(self, directory, serializer, module):
        self.directory = directory
        self.serializer = serializer
        self.module = module
        self.module.fileTranslatorName = self.translator_name
        # Describe the loaded implementation even if files are later updated
        # on disk while Maya still retains this package in memory.
        self._module_sha256 = _sha256(module.__file__)
        self._serializer_sha256 = _sha256(serializer.__file__)
        self._owner = None
        if module.Cast is not serializer.Cast:
            raise RuntimeError("The private CAST importer uses a different serializer")

    @property
    def registered(self):
        return self._owner is not None

    def register(self, plugin):
        """Register only our named translator; never replace external Cast."""
        owner = str(plugin.name())
        if self._owner is not None:
            if self._owner != owner:
                raise RuntimeError(
                    "The private CAST translator is already owned by %s" % self._owner)
            return
        plugin.registerFileTranslator(
            self.translator_name, None, self.module.createCastTranslator)
        self._owner = owner

    def unregister(self, plugin):
        """Only the registering toolkit plugin may remove its translator."""
        if self._owner != str(plugin.name()):
            return
        plugin.deregisterFileTranslator(self.translator_name)
        self._owner = None

    def read(self, path):
        """Read a document; cached documents are read-only within read_session."""
        return self.module.utilityLoadCast(os.fspath(path))

    @contextmanager
    def read_session(self):
        with self.module.utilityCastReadSession():
            yield self

    def options(self, values=None, runtime=None):
        """Scope importer options without touching external settings or cfg."""
        return self.module.utilityOperationOptions(values, runtime)

    def info(self):
        """Return serializable provenance and capabilities for manifests."""
        module_path = os.path.realpath(self.module.__file__)
        serializer_path = os.path.realpath(self.serializer.__file__)
        return {
            "name": "cod-viewmodel-toolkit-private-cast",
            "version": str(self.module.version),
            "translator": self.translator_name,
            "owner": self._owner,
            "module": self.module.__name__,
            "module_path": module_path,
            "module_sha256": self._module_sha256,
            "serializer_path": serializer_path,
            "serializer_sha256": self._serializer_sha256,
            "capabilities": {
                "read_session": callable(getattr(self.module, "utilityCastReadSession", None)),
                "operation_options": callable(getattr(self.module, "utilityOperationOptions", None)),
                "animation_targets": callable(getattr(self.module, "utilityAnimationTargets", None)),
            },
        }


def get_backend(toolkit_plugin_path):
    """Resolve the bundled backend once, including Maya loaders without __file__.

    Multiple entries from the same installation share the private package even
    if Maya executed each toolkit core in a separate Python namespace. Mixing
    two installations in one Maya process is rejected rather than silently
    borrowing the first installation's code. Unload/reload of one installation
    is supported; switching its source requires restarting Maya.
    """
    directory = _source_directory(toolkit_plugin_path)
    package = sys.modules.get(_PACKAGE)
    if package is not None:
        backend = getattr(package, "_backend", None)
        if backend is None:
            raise RuntimeError("The private CAST package is not fully initialized")
        if _identity(backend.directory) != _identity(directory):
            raise RuntimeError(
                "A different toolkit CAST backend is already loaded from %s. "
                "Restart Maya before switching toolkit installations to %s."
                % (backend.directory, directory))
        return backend

    package = types.ModuleType(_PACKAGE)
    package.__package__ = _PACKAGE
    package.__path__ = [directory]
    sys.modules[_PACKAGE] = package
    try:
        serializer = _load_module(_PACKAGE + ".cast", os.path.join(directory, "cast.py"))
        package.cast = serializer
        module = _load_module(_PACKAGE + ".castplugin", os.path.join(directory, "castplugin.py"))
        package.castplugin = module
        package._backend = _Backend(directory, serializer, module)
        return package._backend
    except Exception:
        # Do not retain half-loaded modules after a damaged/missing installation.
        for name in (_PACKAGE + ".castplugin", _PACKAGE + ".cast", _PACKAGE):
            sys.modules.pop(name, None)
        raise
