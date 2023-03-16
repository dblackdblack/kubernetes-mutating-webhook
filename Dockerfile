FROM python:3.11-slim

RUN apt-get update \
	&& apt-get -y install curl procps psmisc

WORKDIR /webhook

COPY ["requirements.txt", "/webhook"]
RUN python3 -m pip install --no-cache-dir --upgrade -r /webhook/requirements.txt

COPY ["main.py", "/webhook"]

USER nobody
CMD ["bash", "-xec", "exec uvicorn main:app --host 0.0.0.0 --port 5000"]
