FROM node:22-alpine

WORKDIR /app

COPY website/package.json /app/website/package.json
RUN npm install --no-audit --no-fund --prefix /app/website

COPY backoffice/package.json /app/backoffice/package.json
RUN npm install --no-audit --no-fund --prefix /app/backoffice

COPY . /app

EXPOSE 5174 3000

CMD ["sh", "/app/start.sh"]