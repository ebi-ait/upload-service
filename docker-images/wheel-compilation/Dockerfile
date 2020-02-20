FROM amazonlinux:2.0.20191217.0

COPY pyswitch /usr/bin/
RUN chmod +x /usr/bin/pyswitch

RUN mkdir -p /opt
COPY aws_setup /opt/
RUN chmod +x /opt/aws_setup

RUN yum update -y &&\
    amazon-linux-extras install -y python3 &&\
    yum install -y git make which

# set up required utilities for building upload service
RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm &&\
    yum install -y jq moreutils gettext unzip

RUN rm /usr/bin/python &&\
    ln -s /usr/bin/python3 /usr/bin/python &&\
    pyswitch 3 &&\
    pip install --user virtualenv

VOLUME /aws/host:ro

ENV DEPLOYMENT_STAGE=dev
ENV AWS_PROFILE=default
ENV AWS_DEFAULT_REGION=us-east-1

CMD /opt/aws_setup && /bin/bash
