from abc import ABC, abstractmethod


class PostProcessor(ABC):
    @abstractmethod
    def is_aplicable_to_agency(self, agency):
        pass

    @abstractmethod
    def is_aplicable_to_dataframe(self, df):
        pass

    @abstractmethod
    def process(self, df):
        pass

    @abstractmethod
    def route_name(self, df):
        pass

    @abstractmethod
    def format_message_records(self, df):
        pass
