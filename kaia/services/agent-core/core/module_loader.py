import importlib
import pkgutil
import logging
from modules.base import BaseModule

logger = logging.getLogger("module_loader")


def load_all_modules() -> list[BaseModule]:
    modules = []
    for _, name, _ in pkgutil.iter_modules(["modules"]):
        if name == "base":
            continue
        try:
            mod = importlib.import_module(f"modules.{name}")
            for attr in dir(mod):
                cls = getattr(mod, attr)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, BaseModule)
                    and cls is not BaseModule
                ):
                    instance = cls()
                    if instance.enabled:
                        modules.append(instance)
                        logger.info(f"Loaded module: {instance.name}")
        except Exception as e:
            logger.error(f"Failed to load module '{name}': {e}")

    return modules
