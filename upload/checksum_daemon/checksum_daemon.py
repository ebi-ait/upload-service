from upload import UploadArea
from .ingest_notifier import IngestNotifier


class ChecksumDaemon:

    RECOGNIZED_S3_EVENTS = ('ObjectCreated:Put', 'ObjectCreated:CompleteMultipartUpload')

    def __init__(self, context):
        self._context = context
        self.log("Ahm ahliiivvve!")

    def consume_event(self, event):
        for record in event['Records']:
            if record['eventName'] not in self.RECOGNIZED_S3_EVENTS:
                self.log(f"WARNING: Unexpected event: {record['eventName']}")
                continue
            file_key = record['s3']['object']['key']
            uploaded_file = self._retrieve_file(file_key)
            self._checksum_file(uploaded_file)
            self._notify_ingest(uploaded_file)

    def _retrieve_file(self, file_key):
        self.log(f"File: {file_key}")
        area_uuid = file_key.split('/')[0]
        filename = file_key[len(area_uuid) + 1:]
        return UploadArea(area_uuid).uploaded_file(filename)

    def _checksum_file(self, uploaded_file):
        uploaded_file.compute_checksums()
        tags = uploaded_file.save_tags()
        self.log(f"Checksummed and tagged with: {tags}")

    def _notify_ingest(self, uploaded_file):
        payload = uploaded_file.info()
        status = IngestNotifier().file_was_uploaded(payload)
        self.log(f"Notified Ingest: payload={payload}, status={status}")

    def log(self, message):
        self._context.log(message)