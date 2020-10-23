# -*- coding: utf-8 -*-

import os
import re
import glob
import json
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

from .table_builder import create_data, search_page_table
from .. import exchanges
from .. import configuration as conf
from ..executors import get_default_executor
from ..models import File, Rule, Job, Table
from ..settings import Session
from ..utils.file import mkdirs, allowed_filename, is_image_file, ocr_image
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
        return render_template("files.html.jinja", files_response=files_response,
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

        if( is_image_file(file) ):
            filepath = ocr_image(filepath )

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
            {"rule_id": rule.rule_id, "rule_name": rule.rule_name} for rule in rules if rule.save_rule
        ]
    return render_template(
        "workspace.html.jinja",
        filename=file.filename,
        imagepaths=imagepaths,
        filedims=filedims,
        imagedims=imagedims,
        detected_areas=detected_areas,
        saved_rules=saved_rules,
        same_as=file.same_as,
        file_id=file_id,
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
        return render_template("rules.html.jinja", saved_rules=saved_rules)
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
            save_rule=True,
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
                "job.html.jinja",
                is_finished=job.is_finished,
                started_at=job.started_at,
                finished_at=job.finished_at,
                datapath=job.datapath,
                data=data,
                search=search_page_table,
                job_id=job_id,
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
        return render_template("jobs.html.jinja", jobs_response=jobs_response)
    file_id = request.form["file_id"]
    rule_id = request.form["rule_id"]
    save_rule = request.form["save_rule"] == "true"
    rule_options = request.form["rule_options"]

    session = Session()
    file = session.query(File).filter(File.file_id == file_id).first()
    rule = None
    if rule_id:
        rule = session.query(Rule).filter(Rule.rule_id == rule_id).first()
    session.close()

    print(rule)
    print(rule.rule_options) if rule_id else print("Rule empty")
    print(rule_options)
    if not rule or Rule.rule_options != rule_options:
        rule_id = generate_uuid()
        created_at = dt.datetime.now()
        rule_name = "_".join([os.path.splitext(file.filename)[0], random_string(6)])

        session = Session()
        r = Rule(
            rule_id=rule_id,
            created_at=created_at,
            rule_name=rule_name,
            rule_options=rule_options,
            save_rule=save_rule
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
    exchanges.publish(message)
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


@views.route("/job/<string:job_id>/table/<string:table_name>/reverse", methods=["POST"])
def reverse(job_id, table_name):
    session = Session()
    table = session.query(Table).filter(Table.job_id == job_id, Table.table_name == table_name).first()
    if table:
        table.reverse = not table.reverse
    else : 
        t = Table(
            table_id=generate_uuid(),
            table_name=table_name,
            reverse=True,
            job_id=job_id,
        )
        session.add(t)
    session.commit()
    session.close()
    flash(f'Table {table_name} Reversed!')
    return redirect(url_for('.jobs', job_id=job_id))


@views.route("/job/<string:job_id>/table/<string:table_name>/delete", methods=["POST"]) # TODO Change post to delete
def delete_table(job_id, table_name):
    session = Session()
    table = session.query(Table).filter(Table.job_id == job_id, Table.table_name == table_name).first()
    if table:
        table.deleted = True
    else : 
        t = Table(
            table_id=generate_uuid(),
            table_name=table_name,
            deleted=True,
            job_id=job_id,
        )
        session.add(t)
    session.commit()
    session.close()
    flash(f'Table {table_name} deleted!')
    return redirect(url_for('.jobs', job_id=job_id))