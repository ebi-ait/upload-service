FROM amazonlinux:2

SHELL ["/bin/bash", "-c"]

RUN yum groupinstall "Development Tools" -y
RUN yum install openssl-devel readline-devel zlib-devel -y

RUN git clone https://github.com/pyenv/pyenv.git ~/.pyenv

RUN /root/.pyenv/bin/pyenv install 3.6.3
RUN /root/.pyenv/versions/3.6.3/bin/python3 -m venv buildenv
