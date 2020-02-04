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

4. Create the S3 Bucket to be used by Terraform to store state. The name of the bucket must match the one specified in
the `TF_STATE` variable of the corresponding `Makefile`. As this S3 Bucket will store sensitive data, it should be set
with least allowable access privilege.

    **Important**: Make sure that the `Makefile` variables are set to point to the correct S3 Bucket. 

5. Define variables for the Terraform build. Copy `_template/terraform.tfvars.example` to `terraform.tfvars.example`:

        cp ../terraform.tfvars.example terraform.tfvars
    
    `terraform.tfvars.example` in the `_template` directory contains most of the common variables shared across all
    deployment environment. Some environments may need specific fields that are not shared by all the other deployment 
    environments.
    
    In most cases, it's easy to just use any of the other previously set up config as reference, and change the values
    slightly based on the deployment environment parameters being setup. Normally, the values only differ by some
    prefix, suffix, etc.
    
    **Important**: Terraform variables are expected to contain secrets and sensitive data. The `terraform.tfvars` file
    should **not** be checked in to version control, and shared to a public repository. Normally, the version control
    system should already be ignoring the file, so no further action is required.
    
    For a background on the configuration options in the `terraform.tfvars`, refer to 
    [the original setup wiki](https://allspark.dev.data.humancellatlas.org/HumanCellAtlas/upload-service/wikis/Deploying-the-Upload-Service-in-a-New-Project#decisions).
    Of a particular note is the `upload_api_api_gateway_id` field which is only set much later in the process. 

6. Upload the variable files to the S3 Bucket.

        make upload-vars
   
7. Define deployment secrets for the new environment.

        echo "export INGEST_API_KEY=<generated-long-string>" > config/deployment_secrets.<deployment_stage>
        
    The `<generated-long-string>` must match the value of `ingest_api_key` in `terraform.tfvars`.
    
8. Set up required roles on AWS.
    
    Upload Service deployment requires a few roles. At the time of writing these are:
    * `ecsInstanceRole`
    * `AWSBatchServiceRole`
    * `AmazonEC2SpotFleetRole`
    * `AWSServiceRoleForEC2Spot`
    * `AWSServiceRoleForEC2SpotFleet`
    
    When deploying to an AWS account where another instance of the Upload Service was previously deployed successfully,
    these roles most likely already exist. To address missing roles, refer to the 
    [AWS Roles Guide](#aws_roles_guide).
    
9. Confirm that the `Makefile` refers to the correct ARNs for the service-linked roles `AWSServiceRoleForEC2Spot` 
and `AWSServiceRoleForEC2SpotFleet`. These are specified under the `import` target.

    The ARNs are available through the AWS Console, navigating to IAM Roles list. Alternatively, the service roles can
    be queried using the the AWS CLI:
    
        aws --profile=embl-ebi iam list-roles --path-prefix /aws-service-role/spot | jq -r '.Roles[].Arn'
        
    *Note*: this guide explicitly specifies the AWS profile for clarity. Alternatively, the `AWS_PROFILE` environment
    variable can be set to the preferred AWS default profile so that the flag doesn't have to be specified every time.
    

### Setting Up Infrastructure with Terraform
 
When the configuration and setup are done, the changes can be applied to the AWS account.

### Setting Up Missing AWS Roles
<a name="aws_roles_guide"></a>

1. AWS Batch Roles
    
    The `ecsInstanceRole` and `AWSBatchServiceRole` roles are automatically created by AWS Batch when spinning up a new
    AWS Batch instance. The quick way to set up these roles is to create a new Batch instance and deleting right after.
    Go to the AWS Console, select Batch service, select Compute environments, and create a new environment. Once the
    new environment is all set, it can be deleted.

2. For the `AmazonEC2SpotFleetRole`, follow [the official guide](https://docs.aws.amazon.com/batch/latest/userguide/spot_fleet_IAM_role.html#spot-fleet-roles-console).

3. Service-linked Roles
    
    `AWSServiceRoleForEC2Spot` and `AWSServiceRoleForEC2SpotFleet` are service linked roles that can be created through
    the AWS CLI:
    
        aws iam create-service-linked-role --aws-service-name spot.amazonaws.com
        aws iam create-service-linked-role --aws-service-name spotfleet.amazonaws.com
