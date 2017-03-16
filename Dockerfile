FROM ubuntu:16.10

LABEL maintainer "https://github.com/Drowrin/Weeabot"

RUN apt-get update \
    && apt-get install python3.6 python3.6-dev python3-pip -y \
    && apt-get install ffmpeg -y \
    && apt-get install libopus-dev -y \
    && apt-get install libffi-dev -y \
    && apt-get install git -y


ADD . /weeabot
WORKDIR /weeabot

RUN python3.6 -m pip install -r requirements.txt

RUN python3.6 -m pip install -U https://github.com/gunthercox/ChatterBot/archive/master.zip#egg=ChatterBot

VOLUME /weeabot/status
VOLUME /weeabot/config
VOLUME /weeabot/images

CMD python3.6 -u Weeabot.py
