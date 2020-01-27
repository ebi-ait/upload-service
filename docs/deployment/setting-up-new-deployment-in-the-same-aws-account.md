## Introduction

These instructions will help you setup a new deployment in the "humancellatlas" AWS account under the `.data.humancellatlas.org` DNS umbrella.

## Prerequisites
* A Linux / Unix / OS X machine to deploy from.
* Installed:
	* Python 3.6
	* Docker (e.g. Docker for Mac)
	* `terraform` (Mac: `brew install terraform`)
	* `jq` (Mac: `brew install jq`)
	* `envsubst` (Mac: `brew install gettext`, add `/usr/local/opt/gettext/bin` to your path)
* Check out the upload-service repo
* Install packages: `pip install -r requirements-dev.txt`
* Install and configure AWS CLI (`pip install awscli ; aws configure`)

## Make Decisions

### Deployment Stage Name
What are you going to call your new deployment stage?  For the purposes of this discussion I am going to call the stage "sam", so the Upload Service for this deployment will live at `upload.sam.data.humancellatlas.org`.
```bash
export DEPLOYMENT_STAGE=sam
```

### VPC CIDR
See note in `terraform.tfvars.example`.  I chose 10.248.0.0/16.

## Create SSL Certificate
You will need an SSL certificate for `*.sam.data.humancellatlas.org`.
1. In the humancellatlas AWS account, AWS Console, Route 53 service, create a new Hosted Zone sam.data.humancellatlas.org`.  Note down the 4 nameserver name provided.
2. Switch to account `hca-prod`.  In Route 53, in hosted zone `data.humancellatlas.org` create an `NS` record for `sam.data.humancellatlas.org` that contains the 4 nameservers listed above.
3. Also in `hca-prod` go to Certificate Manager and create a certificate request for `*.sam.data.humancellatlas.org` and use DNS Validation.  Download or note down the DNS validation CNAME it wants you to create.
4. In account `humancellatlas`, Route 53, hosted zone `sam.humancellatlas.org` create the CNAME as requested.
5. While you wait for your certificate to be approve, follow the rest of this guide.  You won't need the cert until the very end.

## Create a Terraform Configuration for your Deployment

```bash
cd terraform/envs
mkdir sam
cp dev/Makefile dev/main.tf sam
cd sam
ln -s ../dev/variables.tf
ln -s ../dev/terraform.tfvars.example
```

Edit `Makefile` and set:
```
DEPLOYMENT_STAGE=sam
```

Setup `terraform.tfvars`.  Copy the example file:
```bash
cp terraform.tfvars.example terraform.tfvars
```

Then insert all the configuration data we generated in previous steps, together with made-up values for:
* `ingest_api_key`
* `db_username` only use characters [A-Za-z0-9_]
* `db_password`

Ignore `upload_api_api_gateway_id` for now.  We will create that shortly.

Initialize Terraform and save the vars file in S3:
```bash
make init
make upload-vars
```

## Terraform Part I
The Upload Terraform contains contains several assumptions that things already exist,
and some somewhat circular logic. For this reason, when setting up a new deployment,
we need to create some resources with Terraform,
then create resources that rely upon those Terraformed resources, then complete the Terraforming.

First, create the VPC, a bucket to use to deploy Lambdas, and setup the database server:

```bash
cd terraform/envs/sam

# Preload data used in calculations
terraform apply --backup=- --target=data.aws_availability_zones.available

# Create VPC
terraform apply --backup=- --target=module.upload-service.module.upload-vpc.null_resource.vpc

# Create bucket, boot database server, store database secrets
terraform apply --backup=- \
    --target=module.upload-service.aws_s3_bucket.lambda_deployments \
    --target=module.upload-service.module.upload-service-database.aws_secretsmanager_secret_version.database-secrets
```

## Migrate the database (create tables)
Add a stanza for your env to `config/database.ini`:
```
[sam]
sqlalchemy.url =

```

Run the migrations.
```bash
cd ../../..
make db/migrate
```

## Deploy the API Lambda

```bash
cd chalice
```

The Chalice deployment setup we use is a little non-standard -
it has been modified to not require you to keep state files around.
Because of this extra steps are required after the first deployment:
Do a `make clobber` then edit **and check in** `.chalice/config.json` and `.chalice/deployments.json` adding a stanza for your deployment environment to each of these files, e.g.

In .chalice/config.json
```json
    "sam": {
      "api_gateway_stage": "",
      "environment_variables": {}
    }
```

In .chalice/deployed.json
```json
  "sam": {
    "api_handler_name": "upload-api-sam",
    "api_handler_arn": "",
    "rest_api_id": "",
    "region": "us-east-1",
    "api_gateway_stage": "sam",
    "backend": "api",
    "chalice_version": "0.9.0"
  }
```

Now deploy the API Lambda:

```bash
make deploy
```

Find the ID of the REST API you just created.  You can either get this from `.chalice/deployed.json`,
or run `../scripts/get_api_id upload.lambdas.api_server upload-api-sam`.  Plug this ID into `terraform.tfvars` `upload_api_api_gateway_id=`.

## Prepare to Deploy Daemons (this will be done in a moment by Terraform):

```bash
cd ../daemons
make stage

# Create a dummy version number for now.
aws secretsmanager create-secret --name="dcp/upload/${DEPLOYMENT_STAGE}/upload_service_version" --secret-string='{ "upload_service_version": "'foo'" }'
```

## Terraform Part II

```bash
cd ../terraform/envs/sam

# Import the API lambda resources you created outside of Terraform
tf import module.upload-service.aws_lambda_function.upload_api_lambda upload-api-sam
tf import module.upload-service.aws_iam_role.upload_api_lambda upload-api-sam

# Import account-wide IAM stuff
make import

# Finish Terraforming
make apply
```

If you now point a web browser at `https://upload.sam.data.humancellatlas.org` you should see the API browser.

## Testing
To test your deployment run:

```bash
make functional-tests
```

## Subsequent Deploys
```bash
# This command is very noisy.  You can ignore the warnings.
scripts/deploy.sh
```

## Teardown
Empty your buckets. Terraform can’t delete non-empty buckets:
```bash
aws s3 rm s3://org-humancellatlas-upload-lambda-deployment-${DEPLOYMENT_STAGE} --recursive
aws s3 rm s3://org-humancellatlas-upload-${DEPLOYMENT_STAGE} --recursive
```
Delete the things that depend upon the API Gateway.
```bash
terraform destroy --backup=- \
                  --target=module.upload-service.aws_route53_record.upload \
                  --target=module.upload-service.aws_api_gateway_base_path_mapping.status_api \
                  --target=module.upload-service.aws_api_gateway_domain_name.upload
```
Now, using the AWS Console, delete the API Gateway.  This was created by Chalice and is not managed by Terraform.  Navigate to AWS Console -> API Gateway -> upload.lambdas.api_server (find the one with your "stage") -> Resources -> Actions -> Delete API.

Now destroy everything else.  Be aware this takes a while, 10-15 minutes.

```bash
make destroy
```

If you are going to repeat this exercise, *really* delete your secrets, otherwise Terraform gets confused.  Find out the ARN of each of your secrets (deleted or otherwise) then:
```bash
aws secretsmanager delete-secret --secret-id="<arn>" --force-delete-without-recovery
```
