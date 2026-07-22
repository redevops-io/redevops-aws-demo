# Account-level Budgets alarm + out-of-band emergency destroy.
# 80% -> email warning. 100% -> SNS -> Lambda -> CodeBuild `terraform destroy` on the EKS env.
# None of this depends on Mission Runtime / Sidekick / EKS being healthy.

data "aws_caller_identity" "current" {}

# ---- SNS topics ----
resource "aws_sns_topic" "warn" { name = "redevops-demo-budget-warn" }
resource "aws_sns_topic" "destroy" { name = "redevops-demo-budget-destroy" }

resource "aws_sns_topic_subscription" "warn_emails" {
  for_each  = toset(var.budget_notify_emails)
  topic_arn = aws_sns_topic.warn.arn
  protocol  = "email"
  endpoint  = each.value
}

# Budgets must be allowed to publish to the topics.
data "aws_iam_policy_document" "sns_budgets" {
  dynamic "statement" {
    for_each = [aws_sns_topic.warn.arn, aws_sns_topic.destroy.arn]
    content {
      effect    = "Allow"
      actions   = ["SNS:Publish"]
      resources = [statement.value]
      principals {
        type        = "Service"
        identifiers = ["budgets.amazonaws.com"]
      }
    }
  }
}

resource "aws_sns_topic_policy" "warn" {
  arn    = aws_sns_topic.warn.arn
  policy = data.aws_iam_policy_document.sns_budgets.json
}
resource "aws_sns_topic_policy" "destroy" {
  arn    = aws_sns_topic.destroy.arn
  policy = data.aws_iam_policy_document.sns_budgets.json
}

# ---- the cap ----
resource "aws_budgets_budget" "cap" {
  name         = "redevops-demo-monthly-cap"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.warn.arn]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.destroy.arn]
  }
}

# ---- CodeBuild: runs the out-of-band terraform destroy ----
data "aws_iam_policy_document" "codebuild_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codebuild" {
  name               = "redevops-demo-emergency-destroy-cb"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume.json
}

# CodeBuild needs the same broad infra perms to destroy what the deployer created.
resource "aws_iam_role_policy" "codebuild" {
  name   = "codebuild-destroy-inline"
  role   = aws_iam_role.codebuild.id
  policy = data.aws_iam_policy_document.deployer.json
}

resource "aws_iam_role_policy_attachment" "codebuild_logs" {
  role       = aws_iam_role.codebuild.id
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_codebuild_project" "emergency_destroy" {
  name         = "redevops-demo-emergency-destroy"
  service_role = aws_iam_role.codebuild.arn

  artifacts { type = "NO_ARTIFACTS" }

  environment {
    compute_type = "BUILD_GENERAL1_SMALL"
    image        = "aws/codebuild/amazonlinux2-x86_64-standard:5.0"
    type         = "LINUX_CONTAINER"
    environment_variable {
      name  = "REPO_URL"
      value = var.repo_url
    }
    environment_variable {
      name  = "EKS_ENV_PATH"
      value = var.eks_env_path
    }
  }

  source {
    type      = "NO_SOURCE"
    buildspec = <<-BUILDSPEC
      version: 0.2
      phases:
        install:
          commands:
            - curl -fsSL https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_amd64.zip -o /tmp/tf.zip
            - unzip -o /tmp/tf.zip -d /usr/local/bin
        build:
          commands:
            - git clone "$REPO_URL" repo
            - cd "repo/$EKS_ENV_PATH"
            - terraform init -input=false
            - terraform destroy -auto-approve -input=false
    BUILDSPEC
  }
}

# ---- Lambda: SNS(100%) -> StartBuild ----
data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/emergency_destroy.py"
  output_path = "${path.module}/.build/emergency_destroy.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "redevops-demo-emergency-destroy-fn"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    effect    = "Allow"
    actions   = ["codebuild:StartBuild"]
    resources = [aws_codebuild_project.emergency_destroy.arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "lambda-inline"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "emergency_destroy" {
  function_name    = "redevops-demo-emergency-destroy"
  role             = aws_iam_role.lambda.arn
  handler          = "emergency_destroy.handler"
  runtime          = "python3.12"
  timeout          = 30
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  environment {
    variables = { CODEBUILD_PROJECT = aws_codebuild_project.emergency_destroy.name }
  }
}

resource "aws_sns_topic_subscription" "destroy_lambda" {
  topic_arn = aws_sns_topic.destroy.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.emergency_destroy.arn
}

resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.emergency_destroy.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.destroy.arn
}
