# Provisioning requires an exact reviewed base digest, never a mutable tag.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
RUN node -e "if(!process.versions.node.startsWith('24.'))process.exit(1)"
RUN groupadd -g 10000 sandbox && useradd -u 10000 -g 10000 -M sandbox
WORKDIR /opt/f01
RUN npm install --global pnpm@11.25.0 --ignore-scripts
COPY scaffold/ /opt/f01/scaffold/
WORKDIR /opt/f01/scaffold
RUN pnpm install --frozen-lockfile --ignore-scripts && pnpm store prune
RUN ln -s /opt/f01/scaffold/node_modules /opt/f01/node_modules
COPY helpers/ /opt/f01/
RUN chmod -R a-w /opt/f01 && chmod -R a+rX /opt/f01
LABEL f01.recipe="next-web-v1"
USER 10000:10000
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/node", "/opt/f01/idle.mjs"]
