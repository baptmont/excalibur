import re
import time

from .models import File
from .settings import Session


def handle_duplicate_pdfs():
    print("duplicate")
    while True:
        minutes_interval = 10
        time.sleep(60 * minutes_interval)
        session = Session()
        print("Running duplication handling")
        for file in session.query(File).filter(
            File.same_as != None, File.deleted_folder == False
        ):
            try:
                delete_added_pdf_if_duplicated(file)
                file.deleted_folder = True
                session.commit()
            except FileNotFoundError:
                print(f"Inexistent files for {file.file_id}")
            except:
                print(
                    f"An exception occurred when deleting the files for {file.file_id}"
                )
        session.close()


def delete_added_pdf_if_duplicated(file):
    import shutil, time

    if file.same_as is not None:
        time.sleep(5.0)
        path_list = re.split("(\\\\|/)", file.filepath)[:-2]
        folder_path = "/".join(path_list)
        shutil.rmtree(folder_path)
        print(f"Files removed for {file.file_id}")
