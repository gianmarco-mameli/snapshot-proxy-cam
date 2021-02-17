FROM python

RUN pip install opencv-contrib-python-headless requests

WORKDIR /app

ADD main.py .

CMD python -u ./main.py
