# Installation

Install aws package :
```shell
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
```
```shell
unzip awscliv2.zip
```
```shell
sudo ./aws/install
```

# Configuration
Configure your locale aws with your credentials 
```shell
aws configure 
```

Answer the questions :
 - {AWS ID KEY}
 - {AWS SECRET KEY}
 - eu-west-1

Login docker to AWS 
```shell
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin {xxx}.dkr.ecr.eu-west-1.amazonaws.com/consoneo-qrdecode
```
(Replace {xxx} with the aws id)

# Build

Build locally your image 
```shell
docker build --platform linux/amd64 -t docker-image:qrdecode-lambda .
```

Tag your new image 
```shell
docker tag docker-image:qrdecode-lambda {xxx}.dkr.ecr.eu-west-1.amazonaws.com/consoneo-qrdecode:{tag}
```

Push your image on AWS
```
docker push {xxx}.dkr.ecr.eu-west-1.amazonaws.com/consoneo-qrdecode:{tag}
```

# Deploy image on AWS

Go to https://eu-west-1.console.aws.amazon.com/lambda/home?region=eu-west-1#/functions/consoneo-qrdecode?tab=image

Press "Deploy new image", then "Browse images"

Choose the good repository et the last version/tag pushed from docker

Save and enjoy
