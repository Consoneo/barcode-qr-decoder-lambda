FROM public.ecr.aws/lambda/python:3.10

# Copy requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

#install zbar and Install the specified packages
RUN yum install -y make autoconf gettext-devel automake pkgconfig libtool poppler poppler-utils \
&& yum -y clean all  && rm -rf /var/cache \
&& git clone https://github.com/mchehab/zbar.git \
&& cd zbar/ \
&& autoreconf -vfi \
&& ./configure && make && make install && cd - \
&& cp -v /usr/local/lib/libzbar* /var/lang/lib \
&& pip install -r requirements.txt

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "lambda_function.handler" ]
