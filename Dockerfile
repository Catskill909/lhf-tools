# Labor Heritage Media Archive
#
# No dependencies to install: the app is Python standard library only, and the
# front end has no build step. So there is nothing to compile, nothing to pin,
# and no lockfile to drift — the image is the interpreter plus this repo.
#
#   docker build -t lhf-dam .
#   docker run -p 8000:8000 -v lhf-data:/data lhf-dam

FROM python:3.12-slim

# Unbuffered so container logs appear as they happen rather than in bursts;
# no .pyc files since the filesystem is thrown away on each deploy.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/data/lhf.sqlite \
    LHF_HOST=0.0.0.0 \
    PORT=8000

# curl is here for the orchestrator, not for us. Coolify runs its own health
# check inside the container with curl or wget, and python:3.12-slim has
# neither — the first deploy failed with "curl: not found" on every attempt.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# /data is the mount point for the Coolify volume. Everything that must survive
# a redeploy lives here and nowhere else — the rest of the image is disposable.
RUN mkdir -p /data && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# Uses the app's own API, so it reports the database is readable rather than
# merely that a process is listening.
#
# A short grace is now correct: the entrypoint opens the port in about a second
# and fetches the archive in the background, so there is no long window where
# the container is alive but silent. (Coolify overrides this with its own check
# anyway — this one is for plain `docker run` and compose.)
#
# It must read $PORT rather than a literal. Coolify injects PORT from its
# "Ports Exposes" field and that overrides the ENV above — measured 26 August
# 2026, where the container had PORT=3000 while this line probed 8000 and could
# only ever fail. Harmless there because Coolify substitutes its own check, but
# a health check that cannot pass is worse than none.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/facets" -o /dev/null || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["serve"]
