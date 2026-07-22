FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl unzip git ca-certificates openssh-client && rm -rf /var/lib/apt/lists/*
ARG TF_VERSION=1.9.8
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" \
      -o /tmp/tf.zip && unzip /tmp/tf.zip -d /usr/local/bin && rm /tmp/tf.zip
RUN pip install --no-cache-dir ansible-core boto3 awscli fastapi uvicorn kubernetes
RUN curl -fsSL https://dl.k8s.io/release/v1.30.4/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl \
      && chmod +x /usr/local/bin/kubectl
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
# agentic-os apps/infra is mounted at /opt/agentic-os/apps and repo infra/ at /deploy (compose volumes)
EXPOSE 8230
ENTRYPOINT ["/entrypoint.sh"]
