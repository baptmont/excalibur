import os

from .. import configuration as conf
from subprocess import run


def mkdirs(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def allowed_filename(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in conf.ALLOWED_EXTENSIONS
    )


def is_image_file(file):
    filename = file.filename
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ["png", "jpg"]
    )


def ocr_image(filename):
    outfile = '{}.pdf'.format(filename)
    args = [
        "tesseract",
        filename,
        filename,
        "-c", "textord_tablefind_recognize_tables=1",
        "-c", "tessedit_create_pdf=1",
        os.path.join(conf.EXCALIBUR_HOME, "tesseract.config")
        ]
    run(args)
    return outfile
