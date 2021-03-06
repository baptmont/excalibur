import pandas as pd
import re

ignore_words = [
    r"[Pp]artidas?",
    r"[Pp]assage(m|ns)",
    r"[Cc]hegadas?",
    r"DESIGNAÇÃO",
    r"designação",
    r"\(percurso sem parage(m|ns)\)",
]
ignore_expressions = ["^.{,2}$", "^(.{,2}\\n)+.{,2}$", "^\\n$"]
stop_time_regex = r"\d{1,2}(:|,)[0-5]\d"  # TODO test after compile removed
stop_time_regex_single_digit = r"^(\d{1}(:|,)[0-5]\d)"
stop_regex = re.compile(r"[a-zA-ZÀ-ÿ]{3,}")


def split_rows(df_series):
    series = (
        df_series.str.strip()
        .str.split("\\n", expand=True)
        .stack()
        .str.strip()
        .reset_index(drop=True)
    )
    return series


def clean_data(df, ignores_dict=None, split=True):
    df = df.replace(ignores_dict, regex=True) if ignores_dict else df
    try:
        df = pd.concat([split_rows(df[col]) for col in df], axis=1) if split else df
        df = df.replace({"\n": ""})
        df = df.replace({"": pd.NaT})
    except Exception as e:
        print(e)
    df = df.dropna(how="all", axis="index").reset_index(drop=True)  # remove empty rows
    df = df.dropna(how="all", axis="columns").reset_index(
        drop=True
    )  # remove empty columns
    df = df.replace({pd.NaT: "-"})
    return df


def sort_data(df):
    df = df.replace({stop_time_regex_single_digit: r"0\1"}, regex=True)
    cols = df.columns[(df != df.replace(stop_time_regex, "", regex=True)).all()]
    if not cols.empty:  # sort rows
        df = df.sort_values(by=list(cols))
        df = df.reset_index(drop=True)
    else:  # sort columns
        df = df  # TODO sort columns
    return df


def reverse_data(df):
    cols = df.columns[(df != df.replace(stop_regex, "", regex=True)).all()]
    if cols.empty:  # reverse columns
        df = df.iloc[:, ::-1]
    else:  # reverse rows
        df = df.iloc[::-1]
    return df


def get_origin_and_destination(records):  # TODO change to dataframe function
    origin = ("", -1, -1)
    destination = ("", -1, -1)
    for col_id, column in enumerate(records):
        for row_id, item in enumerate(column.values()):
            if re.match(stop_regex, str(item)):
                if (origin[1] >= row_id and origin[2] >= col_id) or (
                    origin[1] == -1 and origin[2] == -1
                ):
                    origin = (item, row_id, col_id)
                if (destination[1] <= row_id and destination[2] <= col_id) or (
                    destination[1] == -1 and destination[2] == -1
                ):
                    destination = (item, row_id, col_id)
    return origin[0], destination[0]
