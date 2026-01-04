
from abc import ABC, abstractmethod
from typing import Optional

from .models import ExtractResult

class BaseExtractor(ABC):
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    @abstractmethod
    def extract(self, path: str) -> ExtractResult:
        """
        Extract text from file.
        Returns ExtractResult object.
        """
        pass
