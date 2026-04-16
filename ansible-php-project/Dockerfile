# Образ control node: Ansible + SSH-клиент (UTF-8 и Linux внутри контейнера).
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    ANSIBLE_CONFIG=/project/ansible.cfg

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /project
