ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache bluez jq git python3 py3-pip

RUN pip3 install --break-system-packages git+https://github.com/slespersen/evseMQTT@main

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
