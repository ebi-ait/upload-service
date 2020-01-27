# Upload from GCS Buckets
The Secondary Analysis Service (Pipelines) first deposits its results in a Google Cloud Storage (GCS) bucket.  Today, because the Upload Service is implemented only in AWS, to upload files, Pipelines must download its result files to a server somewhere, then use the HCA CLI to re-upload them to an S3 bucket (Upload Service Upload Area). 

The Pipelines team desires to be able to Ingest these results files directly from GCS.

## A Little History: Why only AWS?
In designing the Upload Service, we had to decide what an Upload Area would be.  It was originally envisioned that each upload area would be a separate cloud storage bucket.  Unfortunately buckets are a precious resource; AWS says *“By default, you can create up to 100 buckets in each of your AWS accounts.”*.  This 100 limit can be increased, but we’re assuming that when the starting limit is 100, AWS wouldn’t be excited about granting a request for 100,000. 

It was therefore decided that each deployment would have one bucket, and each Upload Area would be a “folder” within that bucket.  There is no actual such thing as a folder in S3, just objects with keys (but AWS Console does simulate folders by recognizing `/` characters as delimiters).   S3 does however allow you to specify authorization permissions for wildcard keys, e.g. `/a/b/c/*`, which has the effect of defining access to a set of keys in a bucket similar to a folder.  Very importantly, this wildcard allows a user to create new files matching that wildcard.

Once this decision was made, Google Cloud Storage (GCS) was evaluated in this context.  Unfortunately the GCS permissions system does not have the ability to grant access to a part of a bucket, that would allow upload of new files. Permissions are either at the bucket level (IAM) or object level (ACLs). 

It was therefore decided that due to the lack of this feature in GCP (and other reasons, like limited resources), AWS alone would be used to implement the Upload Service.

## Options
The ability to upload results files directly from a GCP bucket is still desirable.  The Pipelines team ping us about the occasionally.  With this in mind let us reconsider ways to achieve this.

The possible solutions to this problem fall into two categories:
* solutions that involve copying files from GCS to S3
* solutions that ingest directly from within GCS

### Copying files from GCS -> S3
One possibility is to offload the work of moving files from GCS to S3 from the submitter to the Upload Service.

S3 does not have an innate ability to store files directly from another cloud storage service or arbitrary URL.  The way you upload to S3 is by performing HTTP POSTs.  It is a “push” system and has no ability to “pull”.  There therefore must be an external entity performing the “push”.

For example the DSS has implemented a system to bi-directionally sync files between S3 and GCP.  Files are copied from GCS to S3 by Lambdas in AWS downloading parts from GCS then POSTing them to S3.  The Upload service could implement a similar system (or we could break this functionality out of the DSS and make it a separate service, but let’s no go there… read on).

This approach has the advantage of keeping all the Upload Service code in AWS, making the system simpler.   The downside is that we are now faced with a permissions challenge getting access to the files in GCP.   If this was done purely for the Secondary Analysis service, this permissions problem would be manageable, as Upload could be made aware of the credentials required to access the Pipelines GCS bucket.

### Ingesting Directly from GCS
The DSS has the ability to store files directly from GCS.  If we can implement enough of the Upload Service in GCP, we could avoid data movement from GCS -> S3 entirely.

In considering implementing Upload in GCS, we need to address the following issues:
	* What is an Upload Area, managing authZ and authN for Upload Areas
	* Upload API
	* Checksumming
	* Validation

**What is an Upload Area, authZ and authN**
First let us revisit the problem of “what is an Upload Area” in GCS. It appears that GCS’ limit in buckets per account may be more lax that that of AWS.  GCS docs say: *“There is a per-project rate limit to bucket creation and deletion of approximately 1 operation every 2 seconds, so plan on fewer buckets and more objects in most cases.”*.  This implies we may be able to have more buckets, as long as we don’t create them too quickly.  If we decided to have an Upload Area be an entire Bucket in GCS, and build a queue for creation so we could work around the creation rate-limit, it might be possible to use entire buckets as Upload Areas in GCS.  This would however be slow.  For Pipelines attempting to create 5000 upload areas would take 3 hours - this is too long.  We would therefore have to have a pre-populated pool of Upload Areas to draw from. 

TBD: We should perform an experiment and attempt to create 10,000 buckets in GCS.

**Upload API**
There isn’t a need to run the Upload API in GCP.  Code running in AWS can perform all the GCP operations from there with adequate credentials and authorization.

**Checksumming**
Checksumming will need to be fully implemented in GCP.  We will need a similar architecture where files deposited in the GCS Upload Area are queued for checksumming immediately via a serverless function, or later via a batch process.
This can be accomplished using GCS Triggers / Cloud Pub/Sub Notifications for Google Cloud Storage, Cloud Functions (Lambdas) and the Genomics API (Batch).  Checksumming’s completion API call can call back to the Upload API in AWS, however it will not have access to AWS Secrets Manager so API keys will have to be managed differently.

**Validation**
Validation could also be implemented using the Genomics API, however investigation is required here to see if  / how it can candle very large files.  The validator base image will require some modification to handle file staging differently.