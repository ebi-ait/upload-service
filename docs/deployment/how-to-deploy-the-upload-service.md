# Table of Contents
 * [SPECIAL INSTRUCTIONS FOR UPCOMING DEPLOYMENTS](#special-instructions-for-upcoming-deployments)
 * [Deploying to a Personal Environment](#deploying-to-a-personal-environment)
 * [Deploying to the dev Environment](#deploying-to-the-dev-environment)
 * [Deploying to Integration](#deploying-to-integration)
 * [Deploying to Staging](#deploying-to-staging)
 * [Deploying to the prod Environment](#deploying-to-the-prod-environment)
 * [Rolling Back a Deploy](#rolling-back-a-deploy)
 * [Prerequisites](#prerequisites)
 * [What to Do When Things Go Wrong](#what-to-do-when-things-go-wrong)
 * [Things that are Deployed "Out-of-band"](#things-that-are-deployed-out-of-band)

# SPECIAL INSTRUCTIONS FOR UPCOMING DEPLOYMENTS
`Please do no not promote to integration until https://github.com/HumanCellAtlas/secondary-analysis/issues/628 is complete`

# Deploying to the dev Environment

```bash
# Terraform the environment
export AWS_PROFILE=hca
cd terraform/envs/dev
make apply

# Run CI/CD deploy
git push
or merge into master
```
Monitor the deploy: [GitLab Upload CI builds](https://allspark.dev.data.humancellatlas.org/HumanCellAtlas/upload-service/pipelines)

# Deploying to Integration

If deploying to integration will result in breaking another component, please provide ample warning (at least 1 week) to the relevant components. Create a ticket in their repo with changes required and date on which breaking change will be promoted.

Do no promote to integration if the dcp wide test is failing.

```bash
git co integration
git merge --ff-only master  # always fast-forward

# Optional: Terraform the environment
export AWS_PROFILE=hca
cd terraform/envs/integration
make apply
You may need to manually attach the compute env to a stub batch (and disable it) in the aws console. It will be auto reattached to the correct batch when you rerun make apply
cd ../../..

# Decide on the new version number for Upload using SEMVER:
#   - non-backward-compatible change to external API = major version (+1.x.x)
#   - changes but API is backward compatible = minor version (x.+1.x)
#   - bugfix = micro version (x.x.+1)
# Tag the new version
git tag vx.y.z
git push --tags

# Deploy the code
git push
```
Monitor the deploy: [GitLab Upload CI builds](https://allspark.dev.data.humancellatlas.org/HumanCellAtlas/upload-service/pipelines)

Update the upload version in the components.yml file of the dcp repo on the integration branch
https://github.com/HumanCellAtlas/dcp/blob/integration/components.yml

After a successful deployment to integration, ensure that the next iteration of the dcp wide integration test passes.

# Deploying to Staging
```bash
To deploy version `x.y.z` to staging:

git checkout staging
git merge --ff-only vx.y.z # should always be a fast-forward

Add release notes (using commit messages or by looking at the git diff)
to https://drive.google.com/drive/folders/16BU1y3n1SD7D5Q1NNk0YUgs4NG7ArWiu

# Optional: Terraform the environment
export AWS_PROFILE=hca
cd terraform/envs/staging
make apply
You may need to manually attach the compute env to a stub batch (and disable it) in the aws console. It will be auto reattached to the correct batch when you rerun make apply
cd ../../..

# Deploy the code
git push

# Monitor the deploy
https://allspark.dev.data.humancellatlas.org/HumanCellAtlas/upload-service/pipelines
```
# Deploying to the prod Environment
```bash
# To deploy version `x.y.z` to prod:

git checkout prod
git merge --ff-only vx.y.z  # should always be a fast-forward

Add release notes (using commit messages or by looking at the git diff)
to https://drive.google.com/drive/folders/16BU1y3n1SD7D5Q1NNk0YUgs4NG7ArWiu

# Optional: Terraform the environment
export AWS_PROFILE=hca-prod
cd terraform/envs/prod
make apply
# You may need to manually attach the compute env to a stub batch (and disable it) in the
# AWS console. It will be auto reattached to the correct batch when you rerun make apply
cd ../../..

# Deploy the code
git push

# Monitor the deploy
https://allspark-prod.data.humancellatlas.org/HumanCellAtlas/upload-service/pipelines. 
If you don't see see a job, click the refresh icon at https://allspark-prod.data.humancellatlas.org/HumanCellAtlas/upload-service/settings/repository to mirror the repository to gitlab and kick off a job.
```
# Deploying to a Personal Environment
Deployments to personal environments, are done manually, not by CI/CD.
For the sake of this section let us assume you are deploying to environment "myenv".

```bash
source venv/36/bin/activate
pip install -r requirements-dev.txt
export AWS_PROFILE=hca
export DEPLOYMENT_STAGE=myenv
source config/environment

# Optional: Terraform the environment
cd terraform/envs/myenv
make apply
cd ../../..

# Deploy
make deploy

# Optional (if DB changes): Migrate the database
make db/migrate

# Test the deployment
make functional-tests
```
# Rolling Back a Deploy

Ensure other components of the DCP will not be affected (or contact owners if they also need to rollback)
```bash
# Retrieve the prior tag (if necessary)
git fetch --all --tags --prune 

# Move head of branch to prior tag
git checkout tags/<tag_name> -b <branch_name>

# Run Terraform to revert changes (if necessary)
cd terraform/envs/<env>
make apply

# TBD: what about the database?

# Deploy the code
git push

# Monitor the deploy
https://allspark.dev.data.humancellatlas.org/HumanCellAtlas/upload-service/pipelines
```

# Prerequisites

 * `awscli` installed and working, with profile `hca-id` and `hca` and/or `hca-prod` (as required)
 * Terraform installed
 * AWS administrator to the account to which you want to deploy
 * Python setup, e.g. `source venv/36/bin/activate`
 * A `terraform/envs/{env}/terraform.tfvars` file for the environment
 * Decrypted `config/deployment_secrets.{env}` for the environment

# What to Do When Things Go Wrong

If you're running into any issues with the deployment, check the [playbook](Upload-Service-Release-Playbook) to see if your issue has already been diagnosed/solved before. If the playbook fails you and you're still running into issues, ping #upload-service on Slack.

# Things that are Deployed "Out-of-band"

These things are done occasionally when they change, or when you setup a new environment:

 * EC2 AMI built and deployed to the environment
 * Validation base Docker image deployed to DockerHub
 * Validation Docker image deployed by Ingest (to quay.io usually)
