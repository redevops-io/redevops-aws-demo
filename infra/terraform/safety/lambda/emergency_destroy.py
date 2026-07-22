"""Out-of-band emergency-destroy trigger.

Invoked by SNS when the account Budgets alarm hits 100% of the cap. It starts the
CodeBuild project that runs `terraform destroy` on the demo EKS env — a path that is
fully independent of Mission Runtime, Sidekick and the EKS cluster itself, so it works
even when all of those are unhealthy.
"""
import os

import boto3


def handler(event, context):
    project = os.environ["CODEBUILD_PROJECT"]
    build = boto3.client("codebuild").start_build(projectName=project)
    print(f"emergency-destroy: started CodeBuild {build['build']['id']} for {project}")
    return {"started": build["build"]["id"]}
