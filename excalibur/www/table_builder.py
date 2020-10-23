import re
import json
import pandas as pd

from ..models import Table
from ..settings import Session
from ..utils import data_frame_utils
from ..post_processors.post_processor import PostProcessor
from ..post_processors.default_post_processor import DefaultPostProcessor
from ..post_processors.espirito_santo_post_processor import EspiritoSantoPostProcessor

agency_processors = [EspiritoSantoPostProcessor]

def create_data(job):
    for agency_processor in agency_processors: #agency processor
        if agency_processor(job.agency_name).is_aplicable():
            return _create_data(job, agency_processor)
    return _create_data(job, DefaultPostProcessor)


def _create_data(job, postProcessor=DefaultPostProcessor):
    postProcessor = postProcessor if postProcessor != None else DefaultPostProcessor
    postProcessor = postProcessor if issubclass(postProcessor, PostProcessor) else DefaultPostProcessor
    data = []
    render_files = json.loads(job.render_files)
    regex = r"page-(\d)+-table-(\d)+"
    for k in sorted(render_files, key=lambda x: (int(re.split(regex, x)[1]), int(re.split(regex, x)[2])),):
        if not table_is_deleted(k, job.job_id):
            agency_name = job.agency_name
            df = pd.read_json(render_files[k])
            pp = postProcessor(agency_name)
            pp = pp if pp.is_aplicable() else DefaultPostProcessor(df, agency_name)
            df = pp.process(df)
            if table_is_reversed(k, job.job_id):
                df = data_frame_utils.reverse_data(df)
            columns = df.columns.values
            records = df.to_dict("records")
            route = pp.route_name(df)
            data.append({"title": k, "columns": columns, "records": records, "route": route})
    return data


def table_is_reversed(table_title, job_id):
    table_name = search_page_table(table_title)
    session = Session()
    table = session.query(Table).filter(Table.job_id == job_id, Table.table_name == table_name).first()
    session.close()
    return False if not table else table.reverse


def table_is_deleted(table_title, job_id):
    table_name = search_page_table(table_title)
    session = Session()
    table = session.query(Table).filter(Table.job_id == job_id, Table.table_name == table_name).first()
    session.close()
    return False if not table else table.deleted


def search_page_table(value):
    string = str(value) if value is not None else ""
    regex = r"page-(\d)+-table-(\d)+"
    table = re.search(regex, string)
    if table:
        return str(table.group(0))
    else:
        return ""
