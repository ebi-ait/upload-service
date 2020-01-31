# Upload Service

## Deploying Upload Service on an AWS Account

### Set up and Configuration

1. Switch to the appropriate environment. This can be done through the `config/environment` script. By default, 
this script switches to whatever is set as `DEPLOYMENT_STAGE` or `dev` if the variable is unset. However, this can be 
set by passing a the name of the
target environment.

        source config/environment
        
    Alternatively, to switch to a specific environment, say `staging`,
    
        source config/environment staging
        
2. Configure the new deployment. Switch to the directory in `terrafor/envs` that corresponds to the deployment stage 
in the `terraform/envs` directory, for example `cd terraform/envs/dev` for development environment. When creating a
completely new environment, the directory needs to be added in the `terraform/envs` directory. From here on, this guide
assumes that the target environment has been previously set up. For new deployments, use any of the existent ones as 
guides. At the time of writing, the `dev` directory is the most up-to-date.

3. In `main.tf` of the target environment, configure the `terraform` block to correctly refer to the S3 backend. Also 
ensure that the correct AWS profile is chosen.

4. Define variables for the Terraform build. Copy `_template/terraform.tfvars.example` to `terraform.tfvars.example`:

        cp ../terraform.tfvars.example terraform.tfvars
    
    `terraform.tfvars.example` in the `_template` directory contains most of the common variables shared across all
    deployment environment. Some environments may need specific fields that are not shared by all the other deployment 
    environments.
    
    **Important**: Terraform variables are expected to contain secrets and sensitive data. The `terraform.tfvars`
    should **not** be checked in to version control, and shared to a public repository. Normally, the version control
    system should already be ignoring the file.
    
    For a background on the configuration options in the `terraform.tfvars`, refer to 
    [the original setup wiki](https://allspark.dev.data.humancellatlas.org/HumanCellAtlas/upload-service/wikis/Deploying-the-Upload-Service-in-a-New-Project#decisions).