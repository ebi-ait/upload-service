FROM amazonlinux:2

RUN yum update -y &&\
    yum install -y python3 &&\
    yum install -y git

RUN rm /usr/bin/python &&\
    ln -s /usr/bin/python3 /usr/bin/python &&\
    ln -s /usr/bin/pip3 /usr/bin/pip

CMD /bin/bash
