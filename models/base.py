from abc import ABC, abstractmethod


class BaseModel(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def classes(self) -> list[str]:
        pass

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def detect(self, frame) -> list[dict]:
        pass
