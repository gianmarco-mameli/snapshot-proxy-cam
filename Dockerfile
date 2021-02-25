FROM python:slim

RUN pip install opencv-python-headless requests

WORKDIR /app

ADD main.py .

CMD python -u ./main.py
