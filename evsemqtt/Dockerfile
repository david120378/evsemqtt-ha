ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache bluez jq python3 py3-pip

COPY src/ /app/
RUN pip3 install --break-system-packages /app/

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
