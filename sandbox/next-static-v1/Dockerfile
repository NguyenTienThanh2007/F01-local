# Separate production image, derived from the exact accepted Phase 2B image.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY production.mjs static-serve.mjs /opt/f01/
RUN chmod a-w /opt/f01/production.mjs /opt/f01/static-serve.mjs && chmod a+r /opt/f01/production.mjs /opt/f01/static-serve.mjs
USER 10000:10000
LABEL f01.production-recipe="next-static-v1"
