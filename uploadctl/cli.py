#!/usr/bin/env python3.6

"""
Upload Service Administration Tool

    uploadctl setup|check|teardown   Manage cloud infrastructure
    uploadctl cleanup                Remove old upload areas
    uploadctl test                   Test Upload Service, run uploadctl test -h for more details
"""

import argparse
import os

from .cleanup import CleanupCLI
from .diagnostics import DiagnosticsCLI
from .setup import SetupCLI
from .test import TestCLI


class UploadctlCLI:

    def __init__(self):

        parser = self._setup_argparse()
        args = parser.parse_args()

        if 'command' not in args:
            parser.print_help()
            exit(1)

        elif args.command == 'diag':
            DiagnosticsCLI.run(args)
            exit(0)

        self._check_deployment(args)

        if args.command in ['setup', 'check', 'teardown']:
            SetupCLI.run(args)

        elif args.command == 'test':
            TestCLI.run(args)

        elif args.command == 'cleanup':
            CleanupCLI.run(args)

        exit(0)

    @staticmethod
    def _setup_argparse():
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-d', '--deployment',
                            choices=['dev', 'integration', 'staging', 'prod'],
                            help="operate on this deployment")
        subparsers = parser.add_subparsers()

        CleanupCLI.configure(subparsers)
        DiagnosticsCLI.configure(subparsers)
        SetupCLI.configure(subparsers)
        TestCLI.configure(subparsers)
        return parser

    @staticmethod
    def _check_deployment(args):
        if not args.deployment:
            deployment = os.environ['DEPLOYMENT_STAGE']
            answer = input(f"Use deployment {deployment}? (y/n): ")
            if answer is not 'y':
                exit(1)
        else:
            deployment = args.deployment
            os.environ['DEPLOYMENT_STAGE'] = deployment
        return deployment