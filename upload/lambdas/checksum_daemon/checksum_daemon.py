import json
import os
import re
import uuid
import boto3
from six.moves import urllib
from ...common.upload_area import UploadArea
from ...common.checksum_event import UploadedFileChecksumEvent
from ...common.logging import get_logger
from ...common.logging import format_logger_with_id
from ...common.batch import JobDefinition
from ...common.upload_config import UploadConfig

logger = get_logger(__name__)

KB = 1024
MB = KB * KB
GB = MB * KB

batch = boto3.client('batch')


class ChecksumDaemon:

    RECOGNIZED_S3_EVENTS = ('ObjectCreated:Put', 'ObjectCreated:CompleteMultipartUpload')

    def __init__(self, context):
        self.request_id = context.aws_request_id
        format_logger_with_id(logger, "request_id", self.request_id)
        logger.debug("Ahm ahliiivvve!")
        self.config = UploadConfig()
        self._read_environment()
        self.upload_area = None
        self.uploaded_file = None

    def _read_environment(self):
        self.deployment_stage = os.environ['DEPLOYMENT_STAGE']
        self.job_q_arn = os.environ['CSUM_JOB_Q_ARN']
        self.job_role_arn = os.environ['CSUM_JOB_ROLE_ARN']
        self.docker_image = os.environ['CSUM_DOCKER_IMAGE']
        self.ingest_amqp_server = os.environ['INGEST_AMQP_SERVER']
        self.api_host = os.environ["API_HOST"]

    def consume_event(self, event):
        for record in event['Records']:
            if record['eventName'] not in self.RECOGNIZED_S3_EVENTS:
                logger.warning(f"Unexpected event: {record['eventName']}")
                continue
            file_key = record['s3']['object']['key']
            self._find_file(file_key)
            logger.debug("Scheduling checksumming batch job")
            self.schedule_checksumming(self.uploaded_file)

    def _find_file(self, file_key):
        format_logger_with_id(logger, "file_key", file_key)
        logger.debug(f"File: {file_key}")
        area_uuid = file_key.split('/')[0]
        filename = urllib.parse.unquote(file_key[len(area_uuid) + 1:])
        logger.debug(f"File: {file_key}")
        logger.info({"request_id": self.request_id, "area_uuid": area_uuid,
                    "file_name": filename, "file_key": file_key, "type": "correlation"})
        self.upload_area = UploadArea(area_uuid)
        self.uploaded_file = self.upload_area.uploaded_file(filename)
        self.uploaded_file.fetch_or_create_db_record()

    JOB_NAME_ALLOWABLE_CHARS = '[^\w-]'

    def schedule_checksumming(self, uploaded_file):
        checksum_id = str(uuid.uuid4())
        command = ['python', '/checksummer.py', uploaded_file.s3url]
        environment = {
            'BUCKET_NAME': self.config.bucket_name,
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'INGEST_AMQP_SERVER': self.ingest_amqp_server,
            'API_HOST': self.api_host
        }
        job_name = "-".join(["csum", self.deployment_stage, uploaded_file.upload_area.uuid, uploaded_file.name])
        job_id = self._enqueue_batch_job(queue_arn=self.job_q_arn,
                                         job_name=job_name,
                                         job_defn=self._find_or_create_job_definition(),
                                         command=command,
                                         environment=environment)
        checksum_event = UploadedFileChecksumEvent(file_id=uploaded_file.s3obj.key,
                                                   checksum_id=checksum_id,
                                                   job_id=job_id,
                                                   status="SCHEDULED")
        checksum_event.create_record()

    def _find_or_create_job_definition(self):
        job_defn = JobDefinition(docker_image=self.docker_image, deployment=self.deployment_stage)
        job_defn.find_or_create(self.job_role_arn)
        return job_defn

    def _enqueue_batch_job(self, queue_arn, job_name, job_defn, command, environment):
        job_name = re.sub(self.JOB_NAME_ALLOWABLE_CHARS, "", job_name)[0:128]
        job = batch.submit_job(
            jobName=job_name,
            jobQueue=queue_arn,
            jobDefinition=job_defn.arn,
            containerOverrides={
                'command': command,
                'environment': [dict(name=k, value=v) for k, v in environment.items()]
            }
        )
        logger.info(f"Enqueued job {job_name} [{job['jobId']}] using job definition {job_defn.arn}:")
        logger.info(json.dumps(job))
        return job['jobId']
