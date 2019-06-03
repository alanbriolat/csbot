FROM python:3.7-alpine

VOLUME /app
WORKDIR /app
COPY csbot ./csbot
COPY csbot.*.cfg requirements.txt run_csbot.py docker-entrypoint.sh ./
RUN find . -name '*.pyc' -delete

RUN apk add --no-cache gcc musl-dev libxslt-dev
RUN pip install --no-cache-dir -r requirements.txt

ARG SOURCE_COMMIT
ENV SOURCE_COMMIT $SOURCE_COMMIT

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["./csbot.cfg"]
