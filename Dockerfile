# Ubuntu 24.04 base (not a slim Python image) is deliberate: the Arabic PDF
# export depends on the system's wkhtmltopdf + font stack, and this exact
# combination (Ubuntu 24.04's `wkhtmltopdf` apt package + `fonts-dejavu`)
# is the one this app's Arabic rendering was built and hardened against
# (see README "PDF export for a doctor's visit" for the specific rendering
# bugs that were found and fixed) -- pulling in wkhtmltopdf a different way
# risks reintroducing those bugs or missing Arabic glyph coverage entirely.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        wkhtmltopdf \
        fonts-dejavu \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

# Render (and most free hosting) sets $PORT; default to 8000 for local
# `docker run` testing where no $PORT is provided.
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
