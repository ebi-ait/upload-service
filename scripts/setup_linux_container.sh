#!/usr/bin/env bash

[[ ! -d /root/.aws ]] && /opt/aws_setup

(cd /code && pip install -r requirements-dev.txt)