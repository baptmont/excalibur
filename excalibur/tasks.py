import os
import re
import glob
import json
import logging
import warnings
import datetime as dt
from PIL import Image, ImageChops

from camelot import core
from camelot.parsers import Lattice, Stream
from camelot.utils import text_in_bbox
from camelot.ext.ghostscript import Ghostscript
from .exchanges import publish_new_file_message

from . import configuration as conf
from .models import Job, File, Rule
from .settings import Session
from .utils.file import mkdirs
from .utils.task import get_pages, save_page, get_file_dim, get_image_dim


def split(file_id):
    try:
        session = Session()
        file: File = session.query(File).filter(File.file_id == file_id).first()
        extract_pages, total_pages = get_pages(file.filepath, file.pages)

        (
            filenames,
            filepaths,
            imagenames,
            imagepaths,
            filedims,
            imagedims,
            detected_areas,
        ) = ({} for i in range(7))
        for page in extract_pages:
            # extract into single-page PDF
            save_page(file.filepath, page)

            filename = f"page-{page}.pdf"
            filepath = os.path.join(conf.PDFS_FOLDER, file_id, filename)
            imagename = "".join([filename.replace(".pdf", ""), ".png"])
            imagepath = os.path.join(conf.PDFS_FOLDER, file_id, imagename)

            # convert single-page PDF to PNG
            gs_call = f"-q -sDEVICE=png16m -o {imagepath} -r300 {filepath}"
            gs_call = gs_call.encode().split()
            null = open(os.devnull, "wb")
            with Ghostscript(*gs_call, stdout=null):
                pass
            null.close()

            filenames[page] = filename
            filepaths[page] = filepath
            imagenames[page] = imagename
            imagepaths[page] = imagepath
            filedims[page] = get_file_dim(filepath)
            imagedims[page] = get_image_dim(imagepath)

            lattice_areas, stream_areas = (None for i in range(2))
            # lattice
            parser = Lattice()
            tables = parser.extract_tables(filepath)
            if len(tables):
                lattice_areas = []
                for table in tables:
                    x1, y1, x2, y2 = table._bbox
                    lattice_areas.append((x1, y2, x2, y1))
            # stream
            parser = Stream()
            tables = parser.extract_tables(filepath)
            if len(tables):
                stream_areas = []
                for table in tables:
                    x1, y1, x2, y2 = table._bbox
                    stream_areas.append((x1, y2, x2, y1))

            detected_areas[page] = {"lattice": lattice_areas, "stream": stream_areas}

        file_is_new = True
        same_as = None
        for old_file in session.query(File).filter(
            File.file_id != file_id,
            File.filename == file.filename,
            File.same_as.is_(None),
        ):
            file_is_new = file_is_new and iterate_paths(imagepaths, old_file)
            same_as = same_as if file_is_new else old_file
        if file_is_new:
            file.extract_pages = json.dumps(extract_pages)
            file.total_pages = total_pages
            file.has_image = True
            file.filenames = json.dumps(filenames)
            file.filepaths = json.dumps(filepaths)
            file.imagenames = json.dumps(imagenames)
            file.imagepaths = json.dumps(imagepaths)
            file.filedims = json.dumps(filedims)
            file.imagedims = json.dumps(imagedims)
            file.detected_areas = json.dumps(detected_areas)
            file.same_as = None
            file.deleted_folder = False
            session.commit()
            session.close()
            publish_new_file_message(file)
        else:
            clone_old_file(file, same_as)
            session.commit()
            session.close()

    except Exception as e:
        logging.exception(e)


def get_file_name_from_path(path):
    return re.split("(\\\\|/)", path)[-1]


def iterate_paths(imagepaths, old_file):
    for path1 in imagepaths.values():
        if old_file.imagepaths is None:
            return True
        path2 = [
            path
            for path in json.loads(old_file.imagepaths).values()
            if get_file_name_from_path(path) == get_file_name_from_path(path1)
        ]
        if path2:
            if check_images_are_equal(path1, path2[0]):
                return False
        else:
            return True
    return True


def check_images_are_equal(imagePath1, imagePath2):
    im1 = Image.open(imagePath1)
    im2 = Image.open(imagePath2)
    imDiff = ImageChops.difference(im1, im2)
    imDiff.save("diff.png")
    return True if imDiff.getbbox() is None else False


def clone_old_file(file, old_file):
    file.extract_pages = old_file.extract_pages
    file.total_pages = old_file.total_pages
    file.has_image = True
    file.filenames = old_file.filenames
    file.filepaths = old_file.filepaths
    file.imagenames = old_file.imagenames
    file.imagepaths = old_file.imagepaths
    file.filedims = old_file.filedims
    file.imagedims = old_file.imagedims
    file.detected_areas = old_file.detected_areas
    file.same_as = old_file.file_id
    file.is_ignored = True
    file.deleted_folder = False


def utf_to_html(self, path, **kwargs):
    """Writes Table to an HTML file.

    For kwargs, check :meth:`pandas.DataFrame.to_html`.

    Parameters
    ----------
    path : str
        Output filepath.

    """
    html_string = self.df.to_html(**kwargs)
    with open(path, "w", encoding="utf-8") as file:
        file.writelines('<meta charset="UTF-8">\n')
        file.write(html_string)


core.Table.to_html = utf_to_html  # FIXME very hacky fix by changing dependecy code


def _generate_columns_and_rows(self, table_idx, tk):
    # select elements which lie within table_bbox
    t_bbox = {}
    t_bbox["horizontal"] = text_in_bbox(tk, self.horizontal_text)
    t_bbox["vertical"] = text_in_bbox(tk, self.vertical_text)

    t_bbox["horizontal"].sort(key=lambda x: (-x.y0, x.x0))
    t_bbox["vertical"].sort(key=lambda x: (x.x0, -x.y0))

    self.t_bbox = t_bbox

    text_x_min, text_y_min, text_x_max, text_y_max = self._text_bbox(self.t_bbox)
    rows_grouped = self._group_rows(self.t_bbox["horizontal"], row_tol=self.row_tol)
    rows = self._join_rows(rows_grouped, text_y_max, text_y_min)
    elements = [len(r) for r in rows_grouped]

    if self.columns is not None and self.columns[table_idx] != "":
        # user has to input boundary columns too
        # take (0, pdf_width) by default
        # similar to else condition
        # len can't be 1
        cols = self.columns[table_idx].split(",")
        cols = [float(c) for c in cols]
        cols.insert(0, text_x_min)
        cols.append(text_x_max)
        cols = [(cols[i], cols[i + 1]) for i in range(0, len(cols) - 1)]
    else:
        # calculate mode of the list of number of elements in
        # each row to guess the number of columns
        ncols = max(set(elements))
        if ncols == 1:
            # if mode is 1, the page usually contains not tables
            # but there can be cases where the list can be skewed,
            # try to remove all 1s from list in this case and
            # see if the list contains elements, if yes, then use
            # the mode after removing 1s
            elements = list(filter(lambda x: x != 1, elements))
            if len(elements):
                ncols = max(set(elements))
            else:
                warnings.warn(f"No tables found in table area {table_idx + 1}")
        cols = [(t.x0, t.x1) for r in rows_grouped if len(r) == ncols for t in r]
        cols = self._merge_columns(sorted(cols), column_tol=self.column_tol)
        inner_text = []
        for i in range(1, len(cols)):
            left = cols[i - 1][1]
            right = cols[i][0]
            inner_text.extend(
                [
                    t
                    for direction in self.t_bbox
                    for t in self.t_bbox[direction]
                    if t.x0 > left and t.x1 < right
                ]
            )
        outer_text = [
            t
            for direction in self.t_bbox
            for t in self.t_bbox[direction]
            if t.x0 > cols[-1][1] or t.x1 < cols[0][0]
        ]
        inner_text.extend(outer_text)
        cols = self._add_columns(cols, inner_text, self.row_tol)
        cols = self._join_columns(cols, text_x_min, text_x_max)
    return cols, rows


Stream._generate_columns_and_rows = (
    _generate_columns_and_rows  # FIXME very hacky fix by changing dependecy code
)


def extract(job_id):
    try:
        session = Session()
        job = session.query(Job).filter(Job.job_id == job_id).first()
        rule = session.query(Rule).filter(Rule.rule_id == job.rule_id).first()
        file = session.query(File).filter(File.file_id == job.file_id).first()

        rule_options = json.loads(rule.rule_options)
        flavor = rule_options.pop("flavor")
        pages = rule_options.pop("pages")

        tables = []
        filepaths = json.loads(file.filepaths)
        for p in pages:
            kwargs = pages[p]
            kwargs.update(rule_options)
            kwargs = (
                create_respective_columns(kwargs)
                if flavor.lower() == "stream"
                else kwargs
            )
            parser = (
                Lattice(**kwargs) if flavor.lower() == "lattice" else Stream(**kwargs)
            )
            t = parser.extract_tables(filepaths[p])
            for _t in t:
                _t.page = int(p)
            tables.extend(t)
        tables = core.TableList(tables)

        froot, fext = os.path.splitext(file.filename)
        datapath = os.path.dirname(file.filepath)
        datapath = os.path.join(datapath, job_id)
        for f in ["csv", "excel", "json", "html"]:
            f_datapath = os.path.join(datapath, f)
            mkdirs(f_datapath)
            ext = f if f != "excel" else "xlsx"
            f_datapath = os.path.join(f_datapath, f"{froot}.{ext}")
            tables.export(f_datapath, f=f, compress=True)

        # for render
        jsonpath = os.path.join(datapath, "json")
        jsonpath = os.path.join(jsonpath, f"{froot}.json")
        tables.export(jsonpath, f="json")
        render_files = {
            os.path.splitext(os.path.basename(f))[0]: f
            for f in glob.glob(os.path.join(datapath, "json/*.json"))
        }

        job.datapath = datapath
        job.render_files = json.dumps(render_files)
        job.is_finished = True
        job.finished_at = dt.datetime.now()

        session.commit()
        session.close()
    except Exception as e:
        logging.exception(e)


def create_respective_columns(kwargs):
    if kwargs["columns"] is not None:
        cols = []
        for area in kwargs["table_areas"]:
            x1, _, x2, _ = area.split(",")
            x1 = float(x1)
            x2 = float(x2)
            cols.append(
                ",".join(
                    [
                        column
                        for column in kwargs["columns"][0].split(",")
                        if float(column) > x1 and float(column) < x2
                    ]
                )
            )
        kwargs["columns"] = cols
    return kwargs
