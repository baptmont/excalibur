import os

from .. import configuration as conf
from ..executors import get_default_executor


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
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ["png", "jpg"]


def ocr_image(filename):
    # TODO change tesseract config to a config file
    print("ocr" + filename)
    filename = filename.replace("\\", "/")
    outfile = "{}.pdf".format(filename)
    args = [
        "tesseract",
        filename,
        filename,
        "-c",
        "textord_tablefind_recognize_tables=1",
        "-c",
        "tessedit_create_pdf=1",
        "-c",
        "tessedit_load_sublangs=por+eng",
        "-c",
        "tessedit_ocr_engine_mode=1",
        "-c",
        "pageseg_devanagari_split_strategy=0",
    ]
    print(" ".join(args))

    executor = get_default_executor()
    executor.execute_async(args)
    return outfile
