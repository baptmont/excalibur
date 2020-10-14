FROM  debian:bullseye

ADD . / 

RUN apt-get update; \
  apt-get install -y --no-install-recommends \
  wget \
  unzip \
  python3-pip \
  tesseract-ocr \
  tesseract-ocr-hin \
  ghostscript \
  libsm6; \
  cd Excalibur/  \
  pip3 install  --no-cache-dir ./ ; \
  python3 setup.py install; \
  python3 -m excalibur initdb ;\
  sed -i s/127.0.0.1/0.0.0.0/g ~/excalibur/excalibur.cfg ; 

RUN apt-get install 'ffmpeg'\
    'libsm6'\ 
    'libxext6'  -y

VOLUME [  "/usr/local/lib/python3.8/dist-packages/excalibur/www/static/uploads" ]
EXPOSE 5001
CMD [ "python3", "-m", "excalibur", "webserver" ]
