from  debian:bullseye

run apt-get update; \
  apt-get install -y --no-install-recommends \
  wget \
  unzip \
  python3-pip \
  tesseract-ocr \
  tesseract-ocr-hin \
  ghostscript \
  libsm6; \
  wget 'https://github.com/harish2704/excalibur/archive/feat-tessearct-ocr-integration.zip'; \
  unzip feat-tessearct-ocr-integration.zip; \
  cd excalibur-feat-tessearct-ocr-integration/ ; \
  pip3 install  --no-cache-dir ./ ; \
  python3 setup.py install; \
  python3 -m excalibur initdb ;\
  sed -i s/127.0.0.1/0.0.0.0/g ~/excalibur/excalibur.cfg ; \
  echo " \
tessedit_load_sublangs              hin+eng \n\
tessedit_ocr_engine_mode            1       \n\
textord_tablefind_recognize_tables  1       \n\
pageseg_devanagari_split_strategy   0       \n\
tessedit_create_pdf                 1       \n\
" > ~/excalibur/tesseract.config


VOLUME [  "/usr/local/lib/python3.8/dist-packages/excalibur/www/static/uploads" ]
CMD [ "python3", "-m", "excalibur", "webserver" ]
