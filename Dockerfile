FROM ubuntu:16.10

LABEL maintainer "https://github.com/Drowrin/Weeabot"

RUN apt-get update \
    && apt-get install python3.6 python3.6-dev python3-pip -y \
    && apt-get install ffmpeg -y \
    && apt-get install libopus-dev -y \
    && apt-get install libffi-dev -y

RUN python3.6 -m pip install -r requirements.txt

VOLUME /status
VOLUME /config
VOLUME /images

CMD python3.6 Weeabot.py
