# Oh no! Something is broken/failed!

Choose an option!

[Terraform version needs to be updated](#terraform-version-needs-to-be-updated)

[Terraform variable needs to be changed](#terraform-variable-needs-to-be-changed)

[Compute environment is broken](#compute-environment-is-broken)

[Hot fix on both prod and staging](#prod-is-on-a-hot-fix-staging-also-contains-the-hot-fix)

[Hot fix only on prod](#prod-has-a-hot-fix-staging-does-not-contain-the-hot-fix)

[Error creating Lambda function](#error-message-from-make-apply-error-creating-lambda-function)

## Terraform version needs to be updated
1) Download and install the version of terraform you want from [https://releases.hashicorp.com/terraform/](https://releases.hashicorp.com/terraform/).
2) Delete `terraform/envs/{env}/.terraform` from the upload-service repo.
3) Run `make init` in `terraform/envs/{env}`

After these steps, you can run `make apply` as usual.

## Terraform variable need to be changed
1) Edit the appropriate `terraform.tfvars` file in the correct environment. For example, if you are making changes to the prod environment, edit `terraform/env/{env}/terraform.tfvars`.
2) Run `make upload-vars`
3) Run `make apply`

Running the second step is important; otherwise running `make apply` will just overwrite your changes with the default/stored version. 

## Compute environment is broken
You can tell that your compute environment is broken by going into AWS Batch (dcp-admin), and clicking on "Compute Environments". There will be a little triangle indicating which environments are broken. When this happens, do the following steps `terraform/env/{env}`:

1) In AWS Batch, Job Queues, first disable, then delete any job queues related to the broken compute environments.
2) In AWS Batch, Compute Environments, first disable, then delete the broken job environments.
3) From `terraform/env/{env}`, run `make apply`. This command *will* error out but the purpose is to get the compute environmennt name. Something like "module.upload-service.aws_batch_compute_environment.validation_compute_env".
4) Run `terraform state rm {compute_environment_name_fetched_in_step_3}`.
5) Run `make apply`

Check AWS Batch, Compute Environments to validate that the new compute environments actually spun up as expected. If this error happened while deploying to prod, at this point in time, you can re-run the functional tests again as well.

## Prod is on a hot fix; staging also contains the hot fix
If the hot fix is both in prod and staging and you're trying to update prod to version x.y.z, then run the following commands instead of `git merge --ff-only vx.y.z`:
```bash
git checkout prod
git reset --hard vx.y.z
```
After running `make apply`, you will likely need to push to prod using the command `git push --force` instead of a simple `git push`.

## Prod has a hot fix; staging does not contain the hot fix
TODO

## Error Message from "make apply": Error creating Lambda function
The full error message might look something like this:

"Error creating Lambda function: InvalidParameterValueException: Error occurred while GetObject. S3 Error Code: NoSuchKey. S3 Error Message: The specified key does not exist."

Did you make changes to a daemon recently? If so, run the following commands:
```bash
# First, cd into the changed daemon's directory.
# Second, switch deployment stage to prod.
export DEPLOYMENT_STAGE=prod
# Third, build the new zip file.
make stage
```

Afterwards, head back over to your `upload-service/terraform/envs/env-that-im-currently-deploying-to/` directory to try `make apply` again.

