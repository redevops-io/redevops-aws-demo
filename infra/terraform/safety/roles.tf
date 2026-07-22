# The three roles Sidekick assumes (role assumption IS the security boundary).
# Trust: only the bootstrap principal may assume them. Tighten the deployer policy before
# any non-demo use — it is intentionally broad for a throwaway, isolated demo account.

data "aws_iam_policy_document" "assume_by_bootstrap" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.bootstrap_principal_arn]
    }
  }
}

# ---- deployer: Terraform / EKS / ECR provisioning ----
resource "aws_iam_role" "deployer" {
  name                 = "redevops-demo-deployer"
  assume_role_policy   = data.aws_iam_policy_document.assume_by_bootstrap.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deployer" {
  statement {
    sid    = "ProvisionDemoInfra"
    effect = "Allow"
    # Broad by design for an isolated demo account; scope down for anything shared.
    actions = [
      "ec2:*", "eks:*", "ecr:*", "elasticloadbalancing:*", "autoscaling:*",
      "iam:*", "s3:*", "efs:*", "elasticfilesystem:*", "secretsmanager:*",
      "logs:*", "kms:*", "cloudformation:*", "ssm:*", "sts:GetCallerIdentity",
      "codebuild:*"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deployer" {
  name   = "deployer-inline"
  role   = aws_iam_role.deployer.id
  policy = data.aws_iam_policy_document.deployer.json
}

# ---- agent: AgentCore / Bedrock / runtime tool access ----
resource "aws_iam_role" "agent" {
  name                 = "redevops-demo-agent"
  assume_role_policy   = data.aws_iam_policy_document.assume_by_bootstrap.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "agent" {
  statement {
    sid    = "BedrockAndAgentCore"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream",
      "bedrock:Retrieve", "bedrock:RetrieveAndGenerate",
      "bedrock:ListFoundationModels", "bedrock:GetFoundationModel",
      "bedrock-agentcore:*", "bedrock-agent:*", "bedrock-agent-runtime:*",
      "sts:GetCallerIdentity"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "agent-inline"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent.json
}

# ---- readonly: monitoring · Cost Explorer · CloudWatch · Inspector · Config · Macie ----
resource "aws_iam_role" "readonly" {
  name                 = "redevops-demo-readonly"
  assume_role_policy   = data.aws_iam_policy_document.assume_by_bootstrap.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "readonly" {
  statement {
    sid    = "ObserveOnly"
    effect = "Allow"
    actions = [
      "cloudwatch:Get*", "cloudwatch:List*", "cloudwatch:Describe*",
      "logs:Get*", "logs:Describe*", "logs:FilterLogEvents", "logs:StartQuery", "logs:GetQueryResults",
      "ce:Get*", "ce:List*", "ce:Describe*",
      "inspector2:List*", "inspector2:Get*", "inspector2:BatchGet*",
      "config:Describe*", "config:Get*", "config:List*", "config:SelectResourceConfig",
      "macie2:List*", "macie2:Get*", "macie2:Describe*",
      "securityhub:Get*", "securityhub:List*", "securityhub:Describe*",
      "eks:Describe*", "eks:List*", "ecr:Describe*", "ecr:List*", "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage", "ecr:GetAuthorizationToken",
      "sts:GetCallerIdentity"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "readonly" {
  name   = "readonly-inline"
  role   = aws_iam_role.readonly.id
  policy = data.aws_iam_policy_document.readonly.json
}
