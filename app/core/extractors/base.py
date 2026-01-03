
from abc import ABC, abstractmethod
from typing import Optional

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, path: str) -> Optional[str]:
        """
        Extract text from file.
        Returns text string or None if extraction failed/not supported.
        Should raise exception only on critical failures.
        """
        pass
