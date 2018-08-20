#!/usr/bin/env python3.6

import os, sys, unittest, uuid, json
from unittest.mock import patch

import boto3
import urllib.parse
from botocore.exceptions import ClientError

from upload.lambdas.api_server.validation_scheduler import MAX_FILE_SIZE_IN_BYTES
from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup

from upload.common.checksum_event import UploadedFileChecksumEvent
from upload.common.validation_event import UploadedFileValidationEvent
from upload.common.uploaded_file import UploadedFile
from upload.common.upload_area import UploadArea
from upload.common.database import get_pg_record
from upload.common.upload_config import UploadConfig

if __name__ == '__main__':
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa


class TestApiAuthenticationErrors(UploadTestCaseUsingMockAWS):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Setup app
        with EnvironmentSetup({
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': 'unguessable'
        }):
            self.client = client_for_test_api_server()

    def test_call_without_auth_setup(self):
        # Use a different app instance started without an INGEST_API_KEY
        with EnvironmentSetup({
            'DEPLOYMENT_STAGE': 'test',
            'INGEST_API_KEY': None
        }):
            self.client = client_for_test_api_server()

            response = self.client.post(f"/v1/area/{str(uuid.uuid4())}", headers={'Api-Key': 'foo'})

        self.assertEqual(500, response.status_code)
        self.assertIn("INGEST_API_KEY", response.data.decode('utf8'))

    def test_call_with_unautenticated(self):

        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}")

        self.assertEqual(400, response.status_code)
        self.assertRegex(str(response.data), "Missing header.*Api-Key")

    def test_call_with_bad_api_key(self):

        response = self.client.post(f"/v1/area/{str(uuid.uuid4())}", headers={'Api-Key': 'I-HAXX0RED-U'})

        self.assertEqual(401, response.status_code)


class TestAreaApi(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()
        # Config
        self.config = UploadConfig()
        self.config.set({
            'bucket_name': 'bogobucket',
            'csum_job_q_arn': 'bogo_arn',
            'csum_job_role_arn': 'bogo_role_arn',
            'upload_submitter_role_arn': 'bogo_submitter_role_arn',
        })
        # Environment
        self.deployment_stage = 'test'
        self.api_key = "foo"
        self.environment = {
            'DEPLOYMENT_STAGE': self.deployment_stage,
            'INGEST_API_KEY': self.api_key,
            'INGEST_AMQP_SERVER': 'foo',
            'CSUM_DOCKER_IMAGE': 'bogo_image',
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        # Setup upload bucket
        self.upload_bucket = boto3.resource('s3').Bucket(self.config.bucket_name)
        self.upload_bucket.create()
        # Authentication
        self.authentication_header = {'Api-Key': self.api_key}
        # Setup app
        self.client = client_for_test_api_server()

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    def _create_area(self):
        area_id = str(uuid.uuid4())
        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)
        return area_id

    def _mock_upload_file(self, area_id, filename, contents="foo", content_type="application/json",
                          checksums=None):
        checksums = {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'} if not checksums else checksums
        file1_key = f"{area_id}/{filename}"
        s3obj = self.upload_bucket.Object(file1_key)
        s3obj.put(Body=contents, ContentType=content_type)
        boto3.client('s3').put_object_tagging(Bucket=self.config.bucket_name, Key=file1_key, Tagging={
            'TagSet': [
                {'Key': 'hca-dss-content-type', 'Value': content_type},
                {'Key': 'hca-dss-s3_etag', 'Value': checksums['s3_etag']},
                {'Key': 'hca-dss-sha1', 'Value': checksums['sha1']},
                {'Key': 'hca-dss-sha256', 'Value': checksums['sha256']},
                {'Key': 'hca-dss-crc32c', 'Value': checksums['crc32c']}
            ]
        })
        return s3obj

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_update_file_checksum(self, mock_format_and_send_notification, mock_connect):
        checksum_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        uploaded_file.create_record()
        checksum_event = UploadedFileChecksumEvent(file_id=s3obj.key,
                                                   checksum_id=checksum_id,
                                                   job_id='12345',
                                                   status="SCHEDULED")
        checksum_event.create_record()

        data = {
            "status": "CHECKSUMMING",
            "job_id": checksum_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        record = get_pg_record("checksum", checksum_id)
        self.assertEqual("CHECKSUMMING", record["status"])
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("checksum_started_at"))))
        self.assertEqual(None, record["checksum_ended_at"])
        mock_format_and_send_notification.assert_not_called()

        data = {
            "status": "CHECKSUMMED",
            "job_id": checksum_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_checksum/{checksum_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': area_id,
            'name': 'foo.json',
            'size': 3,
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': "application/json",
            'url': f"s3://{self.config.bucket_name}/{area_id}/foo.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        record = get_pg_record("checksum", checksum_id)
        self.assertEqual("CHECKSUMMED", record["status"])
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("checksum_started_at"))))
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("checksum_ended_at"))))

    @patch('upload.common.uploaded_file.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES + 1)
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_schedule_file_validation_raises_error_if_file_too_large(self, mock_format_and_send_notification,
                                                                     mock_connect):
        area_id = self._create_area()
        self._mock_upload_file(area_id, 'foo.json')
        response = self.client.put(
            f"/v1/area/{area_id}/foo.json/validate",
            headers=self.authentication_header,
            json={"validator_image": "humancellatlas/upload-validator-example"}
        )
        expected_decoded_response_data = '{\n  "status": 400,\n  "title": "File too large for validation"\n}\n'
        self.assertEqual(expected_decoded_response_data, response.data.decode())

        self.assertEqual(400, response.status_code)

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES - 1)
    @patch('upload.lambdas.api_server.v1.area.ValidationScheduler.schedule_validation')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_schedule_file_validation_doesnt_raise_error_for_correct_file_size(self, mock_format_and_send_notification,
                                                                               mock_connect, mock_validate):
        mock_validate.return_value = 4472093160
        area_id = self._create_area()
        self._mock_upload_file(area_id, 'foo.json')
        response = self.client.put(
            f"/v1/area/{area_id}/foo.json/validate",
            headers=self.authentication_header,
            json={"validator_image": "humancellatlas/upload-validator-example"}
        )
        self.assertEqual(200, response.status_code)

    @patch('upload.common.upload_area.UploadedFile.size', MAX_FILE_SIZE_IN_BYTES - 1)
    @patch('upload.lambdas.api_server.v1.area.ValidationScheduler.schedule_validation')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_schedule_file_validation_works_for_hash_percent_encoding(self, mock_format_and_send_notification,
                                                                      mock_connect, mock_validate):
        mock_validate.return_value = 4472093160
        area_id = self._create_area()
        filename = 'green#.json'
        self._mock_upload_file(area_id, filename)
        url_safe_filename = urllib.parse.quote(filename)
        response = self.client.put(
            f"/v1/area/{area_id}/{url_safe_filename}/validate",
            headers=self.authentication_header,
            json={"validator_image": "humancellatlas/upload-validator-example"}
        )
        self.assertEqual(200, response.status_code)

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_unscheduled_status_file_validation(self, mock_format_and_send_notification, mock_connect):
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        uploaded_file.create_record()
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate", headers=self.authentication_header)
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "UNSCHEDULED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_scheduled_status_file_validation(self, mock_format_and_send_notification, mock_connect):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        uploaded_file.create_record()
        validation_event = UploadedFileValidationEvent(file_id=s3obj.key,
                                                       validation_id=validation_id,
                                                       job_id='12345',
                                                       status="SCHEDULED")
        validation_event.create_record()
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate", headers=self.authentication_header)
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "SCHEDULED")

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_validating_status_file_validation(self, mock_format_and_send_notification, mock_connect):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        uploaded_file.create_record()
        validation_event = UploadedFileValidationEvent(file_id=s3obj.key,
                                                       validation_id=validation_id,
                                                       job_id='12345',
                                                       status="SCHEDULED")
        validation_event.create_record()
        data = {
            "status": "VALIDATING",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        record = get_pg_record("validation", validation_id)
        self.assertEqual("VALIDATING", record["status"])
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("validation_started_at"))))
        self.assertEqual(None, record["validation_ended_at"])
        self.assertEqual(None, record.get("results"))
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate", headers=self.authentication_header)
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "VALIDATING")
        mock_format_and_send_notification.assert_not_called()

    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.connect')
    @patch('upload.lambdas.api_server.v1.area.IngestNotifier.format_and_send_notification')
    def test_validated_status_file_validation(self, mock_format_and_send_notification, mock_connect):
        validation_id = str(uuid.uuid4())
        area_id = self._create_area()
        s3obj = self._mock_upload_file(area_id, 'foo.json')
        upload_area = UploadArea(area_id)
        uploaded_file = UploadedFile(upload_area, s3object=s3obj)
        uploaded_file.create_record()
        validation_event = UploadedFileValidationEvent(file_id=s3obj.key,
                                                       validation_id=validation_id,
                                                       job_id='12345',
                                                       status="SCHEDULED")
        validation_event.create_record()
        data = {
            "status": "VALIDATING",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        data = {
            "status": "VALIDATED",
            "job_id": validation_event.job_id,
            "payload": uploaded_file.info()
        }
        response = self.client.post(f"/v1/area/{area_id}/update_validation/{validation_id}",
                                    headers=self.authentication_header,
                                    data=json.dumps(data))
        self.assertEqual(204, response.status_code)
        mock_format_and_send_notification.assert_called_once_with({
            'upload_area_id': area_id,
            'name': 'foo.json',
            'size': 3,
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': "application/json",
            'url': f"s3://{self.config.bucket_name}/{area_id}/foo.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        record = get_pg_record("validation", validation_id)
        self.assertEqual("VALIDATED", record["status"])
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("validation_started_at"))))
        self.assertEqual("<class 'datetime.datetime'>", str(type(record.get("validation_ended_at"))))
        self.assertEqual(uploaded_file.info(), record.get("results"))
        response = self.client.get(f"/v1/area/{area_id}/foo.json/validate", headers=self.authentication_header)
        validation_status = response.get_json()['validation_status']
        self.assertEqual(validation_status, "VALIDATED")

    def test_create_with_unused_upload_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(201, response.status_code)
        body = json.loads(response.data)
        self.assertEqual(
            {'uri': f"s3://{self.config.bucket_name}/{area_id}/"},
            body)

        record = get_pg_record("upload_area", area_id)
        self.assertEqual(area_id, record["id"])
        self.assertEqual(self.config.bucket_name, record["bucket_name"])
        self.assertEqual("UNLOCKED", record["status"])

    def test_create_with_already_used_upload_area_id(self):
        area_id = self._create_area()

        response = self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(201, response.status_code)
        body = json.loads(response.data)
        self.assertEqual(
            {'uri': f"s3://{self.config.bucket_name}/{area_id}/"},
            body)

        record = get_pg_record("upload_area", area_id)
        self.assertEqual(area_id, record["id"])
        self.assertEqual(self.config.bucket_name, record["bucket_name"])
        self.assertEqual("UNLOCKED", record["status"])

    def test_credentials_with_non_existent_upload_area(self):
        area_id = str(uuid.uuid4())

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        self.assertEqual(404, response.status_code)

    def test_credentials_with_existing_locked_upload_area(self):
        area_id = self._create_area()
        UploadArea(area_id).lock()

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        self.assertEqual(409, response.status_code)

    def test_credentials_with_deleted_upload_area(self):
        area_id = self._create_area()
        UploadArea(area_id).delete()

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        self.assertEqual(404, response.status_code)

    def test_credentials_with_existing_unlocked_upload_area(self):
        area_id = self._create_area()

        response = self.client.post(f"/v1/area/{area_id}/credentials")

        data = json.loads(response.data)
        self.assertEqual(['AccessKeyId', 'Expiration', 'SecretAccessKey', 'SessionToken'], list(data.keys()))

    def test_delete_with_id_of_real_non_empty_upload_area(self):
        area_id = self._create_area()

        obj = self.upload_bucket.Object(f'{area_id}/test_file')
        obj.put(Body="foo")

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("DELETED", record["status"])
        with self.assertRaises(ClientError):
            obj.load()

    def test_delete_with_unused_used_upload_area_id(self):
        area_id = str(uuid.uuid4())

        response = self.client.delete(f"/v1/area/{area_id}", headers=self.authentication_header)

        self.assertEqual(404, response.status_code)
        self.assertEqual('application/problem+json', response.content_type)

    def test_locking_of_upload_area(self):
        area_id = self._create_area()
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("UNLOCKED", record["status"])

        response = self.client.post(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("LOCKED", record["status"])

        response = self.client.delete(f"/v1/area/{area_id}/lock", headers=self.authentication_header)

        self.assertEqual(204, response.status_code)
        record = get_pg_record("upload_area", area_id)
        self.assertEqual("UNLOCKED", record["status"])

    def test_put_file_without_content_type_dcp_type_param(self):
        headers = {'Content-Type': 'application/json'}
        headers.update(self.authentication_header)
        area_id = self._create_area()

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        self.assertEqual(400, response.status_code)
        self.assertEqual('application/problem+json', response.content_type)
        self.assertIn("missing parameter \'dcp-type\'", response.data.decode('utf8'))

    def test_put_file(self):
        headers = {'Content-Type': 'application/json; dcp-type="metadata/sample"'}
        headers.update(self.authentication_header)
        area_id = self._create_area()

        response = self.client.put(f"/v1/area/{area_id}/some.json", data="exquisite corpse", headers=headers)

        s3_key = f"{area_id}/some.json"
        o1 = self.upload_bucket.Object(s3_key)
        o1.load()
        self.assertEqual(201, response.status_code)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(json.loads(response.data), {
            'upload_area_id': area_id,
            'name': 'some.json',
            'size': 16,
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/sample"',
            'url': f"s3://{self.config.bucket_name}/{area_id}/some.json",
            'checksums': {
                "crc32c": "FE9ADA52",
                "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
                "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"
            }
        })
        obj = self.upload_bucket.Object(f"{area_id}/some.json")
        self.assertEqual("exquisite corpse".encode('utf8'), obj.get()['Body'].read())

        record = get_pg_record("file", s3_key)
        self.assertEqual(16, record["size"])
        self.assertEqual(area_id, record["upload_area_id"])
        self.assertEqual("some.json", record["name"])

    def test_list_files(self):
        area_id = self._create_area()
        o1 = self._mock_upload_file(area_id, 'file1.json', content_type='application/json; dcp-type="metadata/foo"')
        o2 = self._mock_upload_file(area_id, 'file2.fastq.gz',
                                    content_type='application/octet-stream; dcp-type=data',
                                    checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})

        response = self.client.get(f"/v1/area/{area_id}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertIn('size', data['files'][0].keys())  # moto file sizes are not accurate
        for fileinfo in data['files']:
            del fileinfo['size']
        self.assertEqual(data['files'][0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.config.bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data['files'][1], {
            'upload_area_id': area_id,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.config.bucket_name}/{area_id}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })

    def test_list_files_only_lists_files_in_my_upload_area(self):
        area1_id = self._create_area()
        area2_id = self._create_area()
        area_1_files = ['file1', 'file2']
        area_2_files = ['file3', 'file4']
        [self._mock_upload_file(area1_id, file) for file in area_1_files]
        [self._mock_upload_file(area2_id, file) for file in area_2_files]

        response = self.client.get(f"/v1/area/{area2_id}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertEqual(area_2_files, [file['name'] for file in data['files']])

    def test_get_file_for_existing_file(self):
        area_id = self._create_area()
        filename = 'file1.json'
        s3obj = self._mock_upload_file(area_id, filename)

        response = self.client.get(f"/v1/area/{area_id}/{filename}")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertIn('size', data.keys())  # moto file sizes are not accurate
        del data['size']
        self.assertEqual(data, {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': s3obj.last_modified.isoformat(),
            'content_type': 'application/json',
            'url': f"s3://{self.config.bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })

    def test_get_file_returns_404_for_missing_area_or_file(self):
        response = self.client.get(f"/v1/area/bogoarea/bogofile")
        self.assertEqual(404, response.status_code)

        area_id = str(uuid.uuid4())

        self.client.post(f"/v1/area/{area_id}", headers=self.authentication_header)

        response = self.client.get(f"/v1/area/{area_id}/bogofile")
        self.assertEqual(404, response.status_code)

    def test_put_files_info(self):
        area_id = self._create_area()
        o1 = self._mock_upload_file(area_id, 'file1.json', content_type='application/json; dcp-type="metadata/foo"')
        o2 = self._mock_upload_file(area_id, 'file2.fastq.gz',
                                    content_type='application/octet-stream; dcp-type=data',
                                    checksums={'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'})
        self._mock_upload_file(area_id, 'a_file_in_the_same_area_that_we_will_not_attempt_to_list')

        response = self.client.put(f"/v1/area/{area_id}/files_info", content_type='application/json',
                                   data=(json.dumps(['file1.json', 'file2.fastq.gz'])))

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)
        self.assertEqual(2, len(data))

        self.assertIn('size', data[0].keys())  # moto file sizes are not accurate
        for fileinfo in data:
            del fileinfo['size']

        self.assertEqual(data[0], {
            'upload_area_id': area_id,
            'name': 'file1.json',
            'last_modified': o1.last_modified.isoformat(),
            'content_type': 'application/json; dcp-type="metadata/foo"',
            'url': f"s3://{self.config.bucket_name}/{area_id}/file1.json",
            'checksums': {'s3_etag': '1', 'sha1': '2', 'sha256': '3', 'crc32c': '4'}
        })
        self.assertEqual(data[1], {
            'upload_area_id': area_id,
            'name': 'file2.fastq.gz',
            'last_modified': o2.last_modified.isoformat(),
            'content_type': 'application/octet-stream; dcp-type=data',
            'url': f"s3://{self.config.bucket_name}/{area_id}/file2.fastq.gz",
            'checksums': {'s3_etag': 'a', 'sha1': 'b', 'sha256': 'c', 'crc32c': 'd'}
        })


if __name__ == '__main__':
    unittest.main()