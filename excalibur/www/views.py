# -*- coding: utf-8 -*-

import os
import re
import glob
import json
import threading
import datetime as dt

import pandas as pd
from werkzeug import secure_filename
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    flash)

from excalibur import queue_listener
from .. import configuration as conf
from ..executors import get_default_executor
from ..models import File, Rule, Job
from ..settings import Session
from ..utils.file import mkdirs, allowed_filename
from ..utils.metadata import generate_uuid, random_string


views = Blueprint("views", __name__)


@views.route("/", methods=["GET"])
def index():
    return redirect(url_for("views.files"))


@views.route("/files", methods=["GET", "POST"])
def files():
    if request.method == "GET":
        files_response = []
        files_checked_response = []
        files_ignored_response = []
        session = Session()
        for file in session.query(File).order_by(File.uploaded_at.desc()).all():
            job = (
                session.query(Job)
                .filter(Job.file_id == file.file_id)
                .order_by(Job.started_at.desc())
                .first()
            )

            response = files_ignored_response if file.is_ignored else files_checked_response if job is not None else files_response
            response.append({
                    "file_id": file.file_id,
                    "job_id": job.job_id if job is not None else "",
                    "uploaded_at": file.uploaded_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    "filename": file.filename,
                    "agency_name": file.agency_name,
                    "same_as" : file.same_as,
                })
        session.close()
        return render_template("files.jinja", files_response=files_response,
                               files_checked_response=files_checked_response,
                               files_ignored_response=files_ignored_response)
    print(f"here with {request}")
    file = request.files["file-0"]
    file_id = create_files(file, pages=request.form["pages"])
    return jsonify(file_id=file_id)


def create_files(file, pages="all", agency_name="", url=""):
    print(str(file))
    print(pages)
    if file and allowed_filename(file.filename):
        file_id = generate_uuid()
        uploaded_at = dt.datetime.now()
        filename = secure_filename(file.filename)
        filepath = os.path.join(conf.PDFS_FOLDER, file_id)
        mkdirs(filepath)
        filepath = os.path.join(filepath, filename)
        print(f"Path {filepath}")
        file.save(filepath)

        session = Session()
        f = File(
            file_id=file_id,
            uploaded_at=uploaded_at,
            pages=pages,
            filename=filename,
            filepath=filepath,
            agency_name=agency_name,
            url=url,
            is_ignored = False,
        )
        session.add(f)
        session.commit()
        session.close()

        command = "excalibur run --task {} --uuid {}".format("split", file_id)
        command_as_list = command.split(" ")
        executor = get_default_executor()
        executor.execute_async(command_as_list)

        return file_id


@views.route("/workspaces/<string:file_id>", methods=["GET"])
def workspaces(file_id):
    session = Session()
    file = session.query(File).filter(File.file_id == file_id).first()
    rules = session.query(Rule).order_by(Rule.created_at.desc()).all()
    session.close()
    imagepaths, saved_rules = (None for i in range(2))
    filedims, imagedims, detected_areas = ("null" for i in range(3))
    if file.has_image:
        imagepaths = json.loads(file.imagepaths)
        print(imagepaths)
        for page in imagepaths:
            imagepaths[page] = imagepaths[page].replace(
                os.path.join(conf.PROJECT_ROOT, "www"), ""
            )
            imagepaths[page] = imagepaths[page].replace("\\", "/")
        filedims = file.filedims
        imagedims = file.imagedims
        detected_areas = file.detected_areas
        saved_rules = [
            {"rule_id": rule.rule_id, "rule_name": rule.rule_name} for rule in rules
        ]
    return render_template(
        "workspace.jinja",
        filename=file.filename,
        imagepaths=imagepaths,
        filedims=filedims,
        imagedims=imagedims,
        detected_areas=detected_areas,
        saved_rules=saved_rules,
        same_as = file.same_as,
        file_id = file_id,
    )

@views.route("/rules", methods=["GET", "POST"], defaults={"rule_id": None})
@views.route("/rules/<string:rule_id>", methods=["GET"])
def rules(rule_id):
    if request.method == "GET":
        if rule_id is not None:
            session = Session()
            rule = session.query(Rule).filter(Rule.rule_id == rule_id).first()
            session.close()
            message = "Rule not found"
            rule_options = {}
            if rule is not None:
                message = ""
                rule_options = json.loads(rule.rule_options)
            return jsonify(message=message, rule_options=rule_options)
        session = Session()
        rules = session.query(Rule).order_by(Rule.created_at.desc()).all()
        session.close()
        saved_rules = [
            {
                "rule_id": rule.rule_id,
                "created_at": rule.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                "rule_name": rule.rule_name,
                "rule_options": rule.rule_options,
            }
            for rule in rules
        ]
        return render_template("rules.jinja", saved_rules=saved_rules)
    message = "Rule invalid"
    file = request.files["file-0"]
    if file and allowed_filename(file.filename):
        rule_id = generate_uuid()
        created_at = dt.datetime.now()
        rule_name = os.path.splitext(secure_filename(file.filename))[0]
        rule_options = file.read()
        message = "Rule saved"

        session = Session()
        r = Rule(
            rule_id=rule_id,
            created_at=created_at,
            rule_name=rule_name,
            rule_options=rule_options,
        )
        session.add(r)
        session.commit()
        session.close()
    return jsonify(message=message)


@views.route("/jobs", methods=["GET", "POST"], defaults={"job_id": None})
@views.route("/jobs/<string:job_id>", methods=["GET"])
def jobs(job_id):
    if request.method == "GET":
        if job_id is not None:
            session = Session()
            job = session.query(Job).filter(Job.job_id == job_id).first()
            session.close()
            data = create_data(job)

            return render_template(
                "job.jinja",
                is_finished=job.is_finished,
                started_at=job.started_at,
                finished_at=job.finished_at,
                datapath=job.datapath,
                data=data,
                search=search_page_table,
            )
        jobs_response = []
        session = Session()
        for job in session.query(Job).order_by(Job.started_at.desc()).all():
            file = session.query(File).filter(File.file_id == job.file_id).first()
            jobs_response.append(
                {
                    "filename": file.filename,
                    "job_id": job.job_id,
                    "started_at": job.started_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    "finished_at": job.finished_at.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
        session.close()
        return render_template("jobs.jinja", jobs_response=jobs_response)
    file_id = request.form["file_id"]
    rule_id = request.form["rule_id"]

    session = Session()
    file = session.query(File).filter(File.file_id == file_id).first()
    session.close()

    if not rule_id:
        rule_id = generate_uuid()
        created_at = dt.datetime.now()
        rule_name = "_".join([os.path.splitext(file.filename)[0], random_string(6)])
        rule_options = request.form["rule_options"]

        session = Session()
        r = Rule(
            rule_id=rule_id,
            created_at=created_at,
            rule_name=rule_name,
            rule_options=rule_options,
        )
        session.add(r)
        session.commit()
        session.close()

    job_id = generate_uuid()
    started_at = dt.datetime.now()

    session = Session()
    j = Job(job_id=job_id, started_at=started_at, file_id=file_id, rule_id=rule_id, agency_name=file.agency_name,
            url=file.url)
    session.add(j)
    session.commit()
    session.close()

    command = "excalibur run --task {} --uuid {}".format("extract", job_id)
    command_as_list = command.split(" ")
    executor = get_default_executor()
    executor.execute_async(command_as_list)
    return jsonify(job_id=job_id)


def create_data(job):
    data = []
    render_files = json.loads(job.render_files)
    regex = r"page-(\d)+-table-(\d)+"
    for k in sorted(render_files, key=lambda x: (int(re.split(regex, x)[1]), int(re.split(regex, x)[2])),):
        df = pd.read_json(render_files[k])
        df = clean_data(df)
        columns = df.columns.values
        records = df.to_dict("records")
        route = '{} - {}'.format(*get_origin_and_destination(records))
        data.append({"title": k, "columns": columns, "records": records, "route": route})
    return data

ignore_words = ["[Pp]artidas?", "[Pp]assage(m|ns)", "[Cc]hegadas?","DESIGNAÇÃO","designação"]
stop_time_regex = re.compile(r'\d{1,2}(:|,)[0-5]\d')

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
    print(df.to_string())
    # df = df.apply(lambda x: split_rows(x,df), axis=0)
    return df

def get_origin_and_destination(records):
    origin = ("",-1,-1)
    destination = ("",-1,-1)
    for col_id, column in enumerate(records):
        for row_id, item in enumerate(column.values()):
            if re.match(r"[a-zA-Z]{3,}", str(item)):
                if (origin[1] >= row_id and origin[2] >= col_id) or (origin[1] == -1 and origin[2] == -1):
                    origin = (item, row_id, col_id)
                if (destination[1] <= row_id and destination[2] <= col_id) or (destination[1] == -1 and destination[2] == -1):
                    destination = (item, row_id, col_id)
    return origin[0] , destination[0]


def search_page_table(value):
    string = str(value) if value is not None else ""
    regex = r"page-(\d)+-table-(\d)+"
    table = re.search(regex, string)
    if table:
        return str(table.group(0))
    else:
        return ""


def send_message(job_id, job):
    data = create_data(job)
    for item in data:
        if request.form[f'name_{search_page_table(item["title"] )}']:
            item["name"] = request.form[f'name_{search_page_table(item["title"] )}']
        if request.form.getlist(f'days_{search_page_table(item["title"] )}'):
            item["days"] = request.form.getlist(f'days_{search_page_table(item["title"] )}')
        item["pdf_name"] = job.datapath
        item["agency_name"] = job.agency_name
        item["url"] = job.url
    message = pd.Series(data).to_json(orient='values')
    queue_listener.publish(message)
    flash('Message Sent!')
    return redirect(f"jobs/{job_id}")


@views.route("/download", methods=["POST"])
def download():
    job_id = request.form["job_id"]
    f = request.form["format"]

    session = Session()
    job = session.query(Job).filter(Job.job_id == job_id).first()
    session.close()

    if f.lower() == "send":
        return send_message(job_id, job)
    else:
        datapath = os.path.join(job.datapath, f.lower())
        print("path =" + datapath)
        zipfile = glob.glob(os.path.join(datapath, "*.zip"))[0]

        directory = os.path.join(os.getcwd(), datapath)
        filename = os.path.basename(zipfile)
        return send_from_directory(
            directory=directory, filename=filename, as_attachment=True
        )

@views.route("/ignore", methods=["POST"])
def ignore():
    file_id = request.form["file_id"]
    session = Session()
    file = session.query(File).get(file_id)
    file.is_ignored = True
    session.commit()
    session.close()
    return redirect(f"files")

@views.route("/unignore", methods=["POST"])
def unignore():
    file_id = request.form["file_id"]
    session = Session()
    file = session.query(File).get(file_id)
    file.is_ignored = False
    session.commit()
    session.close()
    return redirect(f"files")