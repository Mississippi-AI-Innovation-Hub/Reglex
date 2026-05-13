"""
AWS SSO session manager for local ingestion runs.

Handles automatic detection of expired SSO credentials and prompts
re-login without losing ingestion progress. All AWS clients are created
through this module so credential refresh is centralized.

Usage:
    from aws_session import AWSSession

    session = AWSSession(profile="<your-aws-profile>")
    s3 = session.client("s3")
    bedrock = session.client("bedrock-runtime")

    # Before a batch of work:
    session.ensure_valid()  # prompts re-login if expired
"""

from __future__ import annotations

import subprocess
import sys
import time

import boto3
import botocore.exceptions


class SSOExpiredError(Exception):
    """Raised when SSO session expires and can't be refreshed."""
    pass


class AWSSession:
    """
    Manages an AWS SSO session with automatic expiry detection.

    Wraps boto3.Session with the SSO profile and provides client
    creation that automatically refreshes when credentials expire.
    """

    def __init__(self, profile: str = "<your-aws-profile>", region: str = "us-east-1"):
        self.profile = profile
        self.region = region
        self._session = None  # type: boto3.Session
        self._clients: dict[str, object] = {}
        self._refresh_session()

    def _refresh_session(self):
        """Create a new boto3 session from the SSO profile."""
        self._session = boto3.Session(
            profile_name=self.profile,
            region_name=self.region,
        )
        # Clear cached clients so they get recreated with new creds
        self._clients.clear()

    def _sso_login(self):
        """
        Handle expired SSO session.

        If running interactively (user's terminal), tries to open browser.
        If running in a managed shell (Claude Code), saves progress and exits
        with instructions to re-login.
        """
        print(f"\n{'='*60}")
        print(f"SSO session expired for profile '{self.profile}'.")
        print(f"{'='*60}\n")

        # Try interactive login first
        try:
            result = subprocess.run(
                ["aws", "sso", "login", "--profile", self.profile],
                check=False,
                timeout=120,  # 2 min timeout for browser auth
            )
            if result.returncode == 0:
                self._refresh_session()
                print("\nSSO session refreshed. Resuming...\n")
                return
        except (subprocess.TimeoutExpired, OSError):
            pass

        # If interactive login failed/timed out, exit with instructions
        print("Could not refresh SSO session automatically.")
        print("Progress has been saved. To resume:")
        print(f"  1. Run: aws sso login --profile {self.profile}")
        print(f"  2. Re-run the pipeline (it will resume from where it stopped)")
        raise SSOExpiredError(f"SSO session expired for profile '{self.profile}'")

    def ensure_valid(self):
        """
        Check if the current SSO session is valid.
        If expired, prompts for re-login and refreshes all clients.

        Call this before starting a batch of work (e.g., every N documents).
        """
        try:
            sts = self._session.client("sts", region_name=self.region)
            sts.get_caller_identity()
        except (
            botocore.exceptions.UnauthorizedSSOTokenError,
            botocore.exceptions.TokenRetrievalError,
            botocore.exceptions.ClientError,
            botocore.exceptions.SSOTokenLoadError,
            botocore.exceptions.NoCredentialsError,
        ):
            self._sso_login()

    def client(self, service_name: str, **kwargs) -> object:
        """
        Get or create a boto3 client for the given service.

        Clients are cached but cleared on credential refresh.
        """
        if service_name not in self._clients:
            self._clients[service_name] = self._session.client(
                service_name,
                region_name=kwargs.get("region_name", self.region),
            )
        return self._clients[service_name]

    def refresh_clients(self):
        """Force refresh all clients (call after SSO re-login)."""
        self._refresh_session()
