import re
import json
import pandas as pd

from ..models import Table
from ..settings import Session
from ..utils import data_frame_utils
from ..post_processors.post_processor import PostProcessor
from ..post_processors.default_post_processor import DefaultPostProcessor
from ..post_processors.espirito_santo_post_processor import EspiritoSantoPostProcessor
from ..post_processors.valpi_post_processor import ValpiPostProcessor

agency_processors = [EspiritoSantoPostProcessor, ValpiPostProcessor]
regex = r"page-(\d)+-table-(\d)+(\.\d+)?"


def create_data(job):
    for agency_processor in agency_processors:  # agency processor
        if agency_processor(job.agency_name).is_aplicable_to_agency(job.agency_name):
            return _create_data(job, agency_processor)
    return _create_data(job, DefaultPostProcessor)


def _create_data(job, postProcessor=DefaultPostProcessor):
    postProcessor = postProcessor if postProcessor is not None else DefaultPostProcessor
    postProcessor = (
        postProcessor
        if issubclass(postProcessor, PostProcessor)
        else DefaultPostProcessor
    )
    data = []
    render_files = json.loads(job.render_files)
    for k in sorted(
        render_files,
        key=lambda x: (int(re.split(regex, x)[1]), int(re.split(regex, x)[2])),
    ):
        try:
            count = 1
            agency_name = job.agency_name
            df = pd.read_json(render_files[k])
            pp = postProcessor(agency_name)
            pp = (
                pp
                if pp.is_aplicable_to_dataframe(df)
                else DefaultPostProcessor(agency_name)
            )
            df = pp.process(df)
            df_dict = df if isinstance(df, list) else [("None", df)]
            for days, df in df_dict:
                title = f"{k}.{count}" if days != "None" else k  # update name of table
                if not table_is_deleted(title, job.job_id):
                    count += 1
                    if table_is_reversed(title, job.job_id):
                        df = data_frame_utils.reverse_data(df)
                    columns = df.columns.values
                    records = df.to_dict("records")
                    route = pp.route_name(df)
                    data.append(
                        {
                            "title": title,
                            "columns": columns,
                            "_records": records,
                            "route": route,
                            "_days": days,
                            "_df": df,
                        }
                    )
        except IndexError as e:
            print("Timetable lacks information")
            print(e)
    return data


def table_is_reversed(table_title, job_id):
    table_name = search_page_table(table_title)
    session = Session()
    table = (
        session.query(Table)
        .filter(Table.job_id == job_id, Table.table_name == table_name)
        .first()
    )
    session.close()
    return False if not table else table.reverse


def table_is_deleted(table_title, job_id):
    table_name = search_page_table(table_title)
    session = Session()
    table = (
        session.query(Table)
        .filter(Table.job_id == job_id, Table.table_name == table_name)
        .first()
    )
    session.close()
    return False if not table else table.deleted


def search_page_table(value):
    string = str(value) if value is not None else ""
    table = re.search(regex, string)
    if table:
        return str(table.group(0))
    else:
        return ""


def format_message(item):
    for agency_processor in agency_processors:  # agency processor
        if agency_processor(item["agency_name"]).is_aplicable_to_agency(
            item["agency_name"]
        ):
            return _format_message(item, agency_processor)
    return _format_message(item, DefaultPostProcessor)


def _format_message(item, postProcessor=DefaultPostProcessor):
    postProcessor = postProcessor if postProcessor is not None else DefaultPostProcessor
    postProcessor = (
        postProcessor
        if issubclass(postProcessor, PostProcessor)
        else DefaultPostProcessor
    )
    agency_name = item["agency_name"]
    pp = postProcessor(agency_name)
    pp = (
        pp
        if pp.is_aplicable_to_dataframe(item["_df"])
        else DefaultPostProcessor(agency_name)
    )
    pp.route = item["name"]
    records = pp.format_message_records(item["_df"])
    return records
