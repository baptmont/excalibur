import pandas as pd
import re

ignore_words = ["[Pp]artidas?", "[Pp]assage(m|ns)", "[Cc]hegadas?","DESIGNAÇÃO","designação","\(percurso sem paragen\)"]
stop_time_regex = re.compile(r'\d{1,2}(:|,)[0-5]\d')
stop_regex = re.compile(r"[a-zA-Z]{3,}")

def split_rows(df_series):
    series = df_series.str.strip().str.split('\\n', expand=True).stack().str.strip().reset_index(drop=True)
    return series

def clean_data(df):
    word_regex = f"({'|'.join(ignore_words)})"
    ignore_words_dict = {word:'' for word in ignore_words}
    df = df.replace(ignore_words_dict, regex=True)
    try:
        df = pd.concat([split_rows(df[col]) for col in df], axis=1)
        df = df.replace({"":pd.NaT})
    except Exception as e:
        print(e)
    df.dropna(how='all',inplace=True, axis='index')
    df.dropna(how='all',inplace=True, axis='columns')
    # df = df.apply(lambda x: split_rows(x,df), axis=0)
    return df

def sort_data(df):
    cols = df.columns[(df != df.replace(stop_time_regex, '', regex=True)).all()]
    print("cols "+str(cols))
    if not cols.empty: #sort rows
        df = df.sort_values(by=list(cols))
    else: #sort columns
        df = df
    return df

def reverse_data(df):
    cols = df.columns[(df != df.replace(stop_regex, '', regex=True)).all()]
    if cols.empty: # reverse columns
        df = df.iloc[:, ::-1]
    else: # reverse rows
        df = df.iloc[::-1]
    return df

def get_origin_and_destination(records):
    origin = ("",-1,-1)
    destination = ("",-1,-1)
    for col_id, column in enumerate(records):
        for row_id, item in enumerate(column.values()):
            if re.match(stop_regex, str(item)):
                if (origin[1] >= row_id and origin[2] >= col_id) or (origin[1] == -1 and origin[2] == -1):
                    origin = (item, row_id, col_id)
                if (destination[1] <= row_id and destination[2] <= col_id) or (destination[1] == -1 and destination[2] == -1):
                    destination = (item, row_id, col_id)
    return origin[0] , destination[0]
