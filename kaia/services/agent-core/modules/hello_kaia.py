from datetime import datetime
from .base import BaseModule, ModuleResult


class HelloKAIA(BaseModule):
    name = "hello_kaia"
    schedule = "every 1 minutes"
    catchup = False

    def run(self, profile: dict) -> ModuleResult:
        return ModuleResult(
            success=True,
            message=f"KAIA is running — {datetime.now():%H:%M:%S}",
        )
