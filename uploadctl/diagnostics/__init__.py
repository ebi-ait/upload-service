from datetime import datetime

import boto3

from .db_dumper import DbDumper


class DiagnosticsCLI:

    @classmethod
    def configure(cls, subparsers):
        diag_parser = subparsers.add_parser('diag', description="Retrieve diagnostic information")
        diag_parser.set_defaults(command='diag')
        diag_subparsers = diag_parser.add_subparsers()

        job_parser = diag_subparsers.add_parser('job', description="Get information about validation job")
        job_parser.set_defaults(command='diag', diag_command='job')
        job_parser.add_argument('validation_id', nargs='?', help="Show data bout this validation job")

        job_parser = diag_subparsers.add_parser('db', description="Dump database records")
        job_parser.set_defaults(command='diag', diag_command='db')
        job_parser.add_argument('upload_area_id', nargs='?', help="Show record for this upload area")
        job_parser.add_argument('filename', nargs='?', help="Show record for this file in the upload area")

    @classmethod
    def run(cls, args):
        if args.diag_command == 'job':
            cls().describe_validation_job(args.validation_id)
        elif args.diag_command == 'db':
            if args.upload_area_id:
                DbDumper().dump_one_area(args.upload_area_id, args.filename)
            else:
                DbDumper().dump_all()

    def __init__(self):
        self.batch = boto3.client('batch')
        self.logs = boto3.client('logs')

    def describe_validation_job(self, validation_id):
        response = self.batch.describe_jobs(jobs=[validation_id])
        for job in response['jobs']:
            try:
                print(f"Job Id             {job['jobId']}")
                print(f"Job Name           {job['jobName']}")
                print(f"Status             {job['status']}")
                print(f"Created at         {self._datetime(job['createdAt'])}")
                print(f"Container Image    {job['container']['image']}")
                print(f"Container Command  {' '.join(job['container']['command'])}")
                print(f"Started at         {self._datetime(job['startedAt'])}")
                print(f"Duration           {(job['stoppedAt'] - job['startedAt'])/1000}s")
                print("Log:")
            except KeyError:
                pass
            if 'logStreamName' in job['container']:
                self._display_log('/aws/batch/job', job['container']['logStreamName'])
            else:
                print("No log yet.")

    def _display_log(self, log_group_name, log_stream_name):
        for event in self.logs.get_log_events(logGroupName=log_group_name, logStreamName=log_stream_name)['events']:
            print("  " + event['message'])

    @staticmethod
    def _datetime(timestamp):
        return datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
