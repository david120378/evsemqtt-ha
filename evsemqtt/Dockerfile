FROM python:3-alpine

RUN apk add --no-cache bluez jq

RUN pip install git+https://github.com/slespersen/evseMQTT@main

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
