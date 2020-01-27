These instructions are aimed at people attempting to setup the Data Coordination Platform (DCP) for project other than the Human Cell Atlas.

## Prerequisites
* A Linux/Unix machine.
* You have followed the `README.md` and setup your development environment.  `make` runs tests cleanly.
* Amazon Web Services setup
	* Familiarity with Amazon Web Services and the AWS Console.
	* An AWS account that has completed activation and setup billing.
		* A VPC. 
			* I like to turn on “Auto Assign Public IP” for it’s subnet(s) so I can SSH in and debug things.
			* Find the VPC ID.
			* Find the ID of the default security group for the VPC.
	* An IAM user:
		* Console and Programmatic access.
		* Attached policy `AdministratorAccess`.
		* Access keys.
	* The AWS CLI installed and configured using the above access keys (e.g. `pip install awscli`).
	* An EC2 Key Pair. 
		* Create a key pair or upload a public SSH key to AWS Console -> Services -> EC2 -> Key Pairs.  I will refer to this as `my-key-pair` below.
* Installed utilities (these are used for deployment):
	* You should already have Python 3.6 and git if you followed the README.
	* Docker (e.g. Docker for Mac)
	* `terraform` (Mac: `brew install terraform`)
	* `jq` (Mac: `brew install jq`)
	* `envsubst` (Mac: `brew install gettext`, add `/usr/local/opt/gettext/bin` to your path.)
* An SSL certificate.   See discussion in section “Decisions” below.

## Decisions
Decide upon a domain name for your DCP deployment.  The DCP contains several services that coordinate by finding each other under a central domain name, e.g. the Human Cell Atlas lives at `.data.humancellatlas.org` and has services including `ingest.data.humancellatlas.org` and `upload.data.humancellatlas.org`.  

Decide upon the “stage” of your first deployment: `dev`, `staging` or `prod`.  The production (`prod`) deployment lives at the above addresses (e.g. for the HCA it is `upload.data.humancellatlas.org`).  It is currently our convention that the pre-production deployments have the stage name inserted between the service name and the domain, e.g.:

    ingest.dev.data.humancellatlas.org
    upload.dev.data.humancellatlas.org
    ingest.staging.data.humancellatlas.org
    upload.staging.data.humancellatlas.org

Note that DNS does not require you to create a new zone (SOA) for a subdomain such as this.  You can just provide hostnames like `upload.staging` in your CNAME records.

Once you have made the above decisions, you will need to source SSL certificate(s) for these domains.  I find it easiest to get a free wildcard certificate for e.g. `*.dev.data.humancellatlas.org` from the AWS Certificate Manager (ACM).  If you don’t use ACM, you still need to import your certificate into it.

Decide on a naming strategy (prefix) for the Upload Service S3 buckets.  This should generate globally unique names for each stage, e.g the HCA uses `org-humancellatlas-upload-`.  Note the dash on the end of the prefix.

Decide which AWS region you are going to use. 

Decide what Amazon Machine Image (AMI) to use for your Batch workers that perform validation.  You need an ECS optimized AMI that has sufficient storage space for the size of the files you will be validating.  The HCA provides an AMI in `us-east-1` region that allocates a 1 TB volume for this purpose: `ami-f7a6ca8d` (`ecso-with-data-vol-v2`).  You can either:

 * build your own AMI using the instructions in `validation/ami/README.md`
 * use the aforementioned AMI if you are using region `us-east-1`
 * copy that AMI to another region if you are using a different region (see [Copying an AMI - Amazon Elastic Compute Cloud](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/CopyingAMIs.html)).

Create an S3 bucket where you wish to store your terraform state.   The HCA uses buckets named with the convention `org-humancellatlas-<account_number>-terraform.  Create this bucket.


## Configuration
For the purposes of this document we will use the following answers to the above decisions:
* Domain `bogodata.org`
* `dev` deployment
* S3 bucket prefix`org-bogodata-`
* AWS region `us-east-1`
* AMI `ami-f7a6ca8d`
* TERRAFORM_STATE_BUCKET=org-bogodata-1-terraform

Save the above information (except the AMI Id, you will use that later) in `config/environment`.  If you don’t already have secrets for this deployment, generate a long random string you can as the Ingest API key and save it in `config/deployment_secrets.dev` as environment variable `INGEST_API_KEY`.  Finally, source this environment information into your shell:

```bash

vi config/environment
# Changes values:
AWS_DEFAULT_REGION="us-east-1"
DCP_DNS_DOMAIN="bogodata.org"
BUCKET_NAME_PREFIX="org-bogadata-"
# Save it.

echo "export INGEST_API_KEY=long-random-string-i-just-generated" > config/deployment_secrets.dev

export DEPLOYMENT_STAGE=dev
source config/environment
source config/deployment_secrets.dev
```

Configure Terraform:

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
vi terraform.tfvars
# Change the value of all variables to the values you have decided/retreived above.
```

## Infrastructure Setup
Setup cloud infrastructure.  This 
You only need to perform these steps one, not on each deploy.

```bash
# Initialize Terraform
cd terraform/envs/dev
export TERRAFORM_STATE_BUCKET=org-bogodata-1-terraform
make init
# Create service-linked-roles that Terraform cannot do
aws iam create-service-linked-role --aws-service-name spot.amazonaws.com
aws iam create-service-linked-role --aws-service-name spotfleet.amazonaws.com
# Advise terraform of the existence of these two roles:
make import
# Deploy infrastructure
make apply
```

Deploy code:

```bash
cd $PROJECT_ROOT

# This command is very noisy.  Accept the policies and ignore the warnings.
make deploy

# Deploying creates a lot of temporary files which clutter up your Git repo.
# You can clean them up with:
make clobber
```

Setup remaining infrastructure:

```bash
scripts/uploadctl setup
```

## Setup DNS

Go to AWS Console -> Services -> API Gateway -> Custom Domain Names.  Find the “Target Domain Name” of your deployment.  Using whatever system you use to mange your DNS, add a CNAME or alias for `upload.dev.bogodata.org` that points to the `<something>.cloudfront.net` domain name you noted above.

Wait about an hour.  It takes a while for CloudFront to propagate this configuration all around the world.

If you now point a web browser at `http://upload.dev.bogodata.org` you should see the API browser.

## Setup the DCP CLI

Install the CLI and configure it to use your buckets and API endpoints (not required for HCA):

```bash
pip install hca
# Configure it to use your Upload Service
mkdir -p ~/.config/hca
echo '{                                
  "upload": {
    "bucket_name_template": "${BUCKET_NAME_PREFIX}{deployment_stage}",
    "upload_service_api_url_template": "https://${SERVICE_NAME}.{deployment_stage}.${DCP_DNS_DOMAIN}/v1"
  }
}' | envsubst > ~/.config/hca/config.json
```

The `hca` script that is installed may be renamed to something else without affecting its behavior.

## Testing Everything is Setup Correctly
There are several ways we can test to see that things are working correctly, without having to integrate with the Ingest Service.

### Testing the Upload API
You already saw that pointing a web browser at `http://upload.dev.bogodata.org` should show the API browser. 

You can also just talk directly to the API with, e.g. curl:
```bash
curl https://upload.dev.bogodata.org/v1/area/x
{
  "status": 404,
  "title": "Staging Area Not Found"
}
```

Finally, there is a script that exercises most of the API endpoints.  It cleans up after itself so is save to run in any deployment:

```bash
scripts/demo.sh dev
```

After running `demos.sh`, it is worthwhile going to the AWS Console -> Services -> CloudWatch -> Logs and taking a look at the most recent log groups for `/aws/lambda/upload*`.

### Testing the Checksum Daemon
When watching the `demo.sh` script operate, look for checksums on the `LICENSE` file.  This indicates the checksum daemon is working.

### Testing the Batch Infrastructure
You may run an arbitrary docker image in the validation Batch infrastructure using the following command:

```bash
scripts/uploadctl -d dev test batch alpine echo "Hello World"
```

Note that this will take approximately 10 minutes to run, as Batch appears to have a 5-10 minute “settle” time, and it takes a few minutes to boot a server and start the job.  Go into the AWS Console and follow along in the Batch, Elastic Container Service and EC2 pages as Batch slowly decides to spin up a server and run your job.  You can see the output in the log for that job in the Batch console.

If you are doing active development on validators, expect a lot of data to be Ingested soon, or just have pots of money you need to divest yourself of, you can greatly speed up validation by always having one server waiting for validation jobs.  To do this increase `minvCpus` for your compute environment as follows:

```bash
aws batch update-compute-environment --compute-environment dcp-upload-dev --compute-resources minvCpus=2
```

Tune it back down to 0 to stop that server.

### Testing the Validation API
You can also use the REST API to request a file validation.  Validators are simple docker images.  There is an example validator image that decides that files with an even number of bytes are valid and files with an odd number of bytes are invalid.  The source for this image is in the `validation/docker-images` folder, however you can just use it from DockerHub.  To perform this test I normally start the `demo.sh` script, kill it after it has created an area and uploaded the `LICENSE` file, then interact with the Upload API as follows:

```bash
AREA_UUID="deadbeef-dead-dead-dead-beeeeeeeeeef"
FILE="LICENSE"
curl -X PUT -H "Api-Key: ${INGEST_API_KEY}" \
            -H "content-type: application/json" \
            -d '{"validator_image": "humancellatlas/upload-validator-example"}' \
            https://upload.dev.bogodata.org/v1/area/${AREA_UUID}/${FILE}/validate
```

To see the results go to AWS Console -> CloudWatch -> Logs -> `/aws/batch/job`.


## Subsequent Deployments
After the first time, just do the following:

```bash
# This command is very noisy.  You can ignore the warnings.
make deploy
```

## Teardown
To remove all of this infrastructure:

```bash
scripts/uploadctl -d dev teardown
```
