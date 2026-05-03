from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ModuleResult:
    success: bool
    items: list = field(default_factory=list)
    message: str = ""
    requires_approval: bool = False
    proactive: bool = False


class BaseModule(ABC):
    name: str = ""
    schedule: str = ""
    catchup: bool = False
    enabled: bool = True

    @abstractmethod
    def run(self, profile: dict) -> ModuleResult:
        pass

    def on_feedback(self, item_id: str, feedback: str):
        pass

    def should_notify_proactively(self, item: dict, profile: dict) -> bool:
        return False
