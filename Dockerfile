FROM ubuntu:16.10

LABEL maintainer "https://github.com/Drowrin/Weeabot"

RUN sudo apt-get update \
    && sudo apt-get install python3.6 python3.6-dev python3-pip -y \
    && sudo apt-get install ffmpeg -y \
    && sudo apt-get install libopus-dev -y \
    && sudo apt-get install libffi-dev -y

ADD . /weeabot
WORKDIR /weeabot

RUN sudo python3.6 -m pip install -r requirements.

VOLUME /weeabot/status
VOLUME /weeabot/config

CMD python3.6 Weeabot.py
