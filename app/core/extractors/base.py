
from abc import ABC, abstractmethod
from typing import Optional

class BaseExtractor(ABC):
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    @abstractmethod
    def extract(self, path: str) -> Optional[str]:
        """
        Extract text from file.
        Returns text string or None if extraction failed/not supported.
        Should raise exception only on critical failures.
        """
        pass
