## Table of Contents

Some of these link to other pages.  Some of them are links to headings below.

* Deployment
  * [[How to Deploy the Upload Service]]
  * [How to roll back a deployment](how-to-deploy-the-upload-service.md#rolling-back-a-deploy)
  * [Troubleshooting deployments](Upload-Service-Release-Playbook)
* Operation
  * [Monitoring Upload Service Activity](#monitoring-upload-service-activity)
  * [[Investigating Problems]]
  * [How to Press the Big Red Button](#how-to-press-the-big-red-button)
* Background
  * [Upload Service Architecture](https://docs.google.com/document/d/10iv1wS3HB9R5dJb8_Bl_i9VvQZpFp5SMBEUZx6WNprI/edit#heading=h.a5voeq902t5y)

## Operation
### Monitoring Upload Service Activity
There is a dashboard for each environment, showing aggregate avtivity:
* On metrics.dev.data.humancellatlas.org: [dev](https://metrics.dev.data.humancellatlas.org/d/upload-dev/upload-dev), [integration](https://metrics.dev.data.humancellatlas.org/d/upload-integration/upload-integration), [staging](https://metrics.dev.data.humancellatlas.org/d/upload-staging/upload-staging)
* On metrics.data.humancellatlas.org: [prod](https://metrics.data.humancellatlas.org/d/upload-prod/upload-prod)

`TBD - walk-through, or what to look for, in these dashboards.`

Logs for Upload may be found on the Kibana server: [dev/integration/staging](https://logs.dev.data.humancellatlas.org/_plugin/kibana/app/kibana), [prod](https://logs.data.humancellatlas.org/_plugin/kibana/app/kibana)

Upload log groups:
* `/aws/lambda/upload-api-prod`
* `/aws/lambda/dcp-upload-csum-prod`
* `/aws/lambda/dcp-upload-validaton-scheduler-prod`
* `/aws/lambda/dcp-upload-area-deletion-prod`
* `/aws/lambda/dcp-upload-batch-watcher-prod`
* `/aws/lambda/dcp-upload-health-check-prod`
* `/aws/batch/job`

### How to Press the Big Red Button
In the event that the Upload Service needs to be completely stopped, use the following procedure:

In your checked out upload-service git repo, with appropriate AWS keys setup, run:
```
scripts/uploadctl runlevel stop
```
This will quiesce the Upload Service by:
* Throttling all Lambdas to 0 (except the health-check daemon)
* Setting the status of AWS Batch queues to `DISABLED`
* Setting the status of AWS Batch Clusters to `DISABLED`

The status of the service my be queried by running:

```
scripts/uploadctl runlevel status
```

Service my be resumed by running:
```
scripts/uploadctl runlevel start
```
