from ..utils import data_frame_utils
from .post_processor import PostProcessor


class DefaultPostProcessor(PostProcessor):
    def __init__(self, agency) -> None:
        pass

    def is_aplicable_to_agency(self, agency=None):
        return True

    def is_aplicable_to_dataframe(self, df=None):
        return True

    def process(self, df):
        ignores_dict = {
            word: ""
            for word in data_frame_utils.ignore_words
            + data_frame_utils.ignore_expressions
        }
        df = data_frame_utils.clean_data(df, ignores_dict)
        df = data_frame_utils.sort_data(df)
        return df

    def route_name(self, df):
        records = df.to_dict("records")
        return "{} - {}".format(*data_frame_utils.get_origin_and_destination(records))

    def format_message_records(self, df):
        return df.to_dict("records")
