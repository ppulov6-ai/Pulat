FROM python:3.13-alpine AS build
WORKDIR /app
COPY src src
COPY build-site.py .
RUN python build-site.py

FROM node:24-alpine
WORKDIR /app
COPY --from=build /app/dist dist
COPY drizzle drizzle
COPY vps/server.mjs vps/server.mjs
RUN mkdir /data && chown node:node /data
USER node
ENV LISTEN_HOST=0.0.0.0
CMD ["node","vps/server.mjs"]
