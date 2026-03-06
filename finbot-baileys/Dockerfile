FROM node:18-alpine

WORKDIR /app

# Instalar Chromium e dependências necessárias para o Puppeteer
RUN apk add --no-cache \
      chromium \
      nss \
      freetype \
      harfbuzz \
      ca-certificates \
      ttf-freefont

# Pular o download do Chromium pelo Puppeteer, pois usaremos o instalado no sistema
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

# Instalar dependências
COPY package.json package-lock.json* ./
RUN npm install --production

# Copiar código fonte
COPY . .

# Expor porta
EXPOSE 3000

# Comando de inicialização
CMD ["node", "server.js"]
