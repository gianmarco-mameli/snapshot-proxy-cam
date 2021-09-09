# Difficulty to install both ARM & x64, I make a custom install

FROM debian:buster-slim
RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends python3-opencv python3-pip \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && ln -s /usr/bin/pip3 /usr/bin/pip

# CMD ["python3"]

RUN pip install requests

WORKDIR /app

ADD main.py .

USER nobody

CMD python -u ./main.py

# FROM python:slim

# RUN apt-get update

# RUN apt-get install -y cmake
# RUN apt-get install -y gcc g++
# RUN apt-get install -y python3-dev python3-numpy

# RUN apt-get install -y libavcodec-dev libavformat-dev libswscale-dev
# RUN apt-get install -y libgstreamer-plugins-base1.0-dev libgstreamer1.0-dev

# RUN apt-get install -y libgtk-3-dev git

# WORKDIR /toto/tata

# RUN git clone https://github.com/opencv/opencv.git

# WORKDIR /toto/tata/opencv/build

# RUN cmake ../

# RUN make
