ARG BUILD_ARCH=amd64
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest

RUN apk add --no-cache bluez jq python3 py3-pip

COPY src/ /app/
RUN pip3 install --break-system-packages /app/
ENV PYTHONPATH=/app

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
