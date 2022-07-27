FROM nginx:latest
LABEL mainterner="joeyhwong@gknow.cn"

ENV SERVER_NAME ""
ENV NODE_ENV production
ENV ICESERVER ""
ENV VUE_APP_TITLE "RoboArtisan Teleoperation"
ENV VUE_APP_SIGNALING_SERVER_URL ""
ENV VUE_APP_VERSION "1"

COPY dist/ /usr/share/nginx/html/
COPY nginx.conf.template /etc/nginx/nginx.conf.template

CMD ["/bin/sh" , "-c" , "envsubst '$VUE_APP_SIGNALING_SERVER_URL $SERVER_NAME $ICESERVER' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && exec nginx -g 'daemon off;'"]
