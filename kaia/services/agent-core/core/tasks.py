import logging
from core.celery_app import app
from core.module_loader import load_all_modules
from core.catchup import record_run

logger = logging.getLogger("tasks")


@app.task(name="tasks.run_module", bind=True, max_retries=2)
def run_module(self, module_name: str, catchup: bool = False):
    modules = {m.name: m for m in load_all_modules()}
    module = modules.get(module_name)

    if not module:
        logger.error(f"Module not found: {module_name}")
        return

    prefix = "[catchup] " if catchup else ""
    logger.info(f"{prefix}Running module: {module_name}")

    try:
        result = module.run(profile={})
        record_run(module_name, result.success)
        if result.message:
            logger.info(f"{module_name}: {result.message}")
        return {"success": result.success, "message": result.message}
    except Exception as exc:
        logger.error(f"{module_name} failed: {exc}")
        record_run(module_name, False)
        raise self.retry(exc=exc, countdown=60)
