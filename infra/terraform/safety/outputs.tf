# Copy these into Vault at secret/redevops/aws-demo/config after apply.
output "account_id" { value = data.aws_caller_identity.current.account_id }
output "region" { value = var.region }
output "deploy_role_arn" { value = aws_iam_role.deployer.arn }
output "agent_role_arn" { value = aws_iam_role.agent.arn }
output "readonly_role_arn" { value = aws_iam_role.readonly.arn }

output "budget_warn_topic_arn" { value = aws_sns_topic.warn.arn }
output "budget_destroy_topic_arn" { value = aws_sns_topic.destroy.arn }
output "emergency_destroy_project" { value = aws_codebuild_project.emergency_destroy.name }

output "vault_write_hint" {
  description = "One-liner to persist the role ARNs into Vault (run with a privileged Vault token)."
  value = format(
    "vault kv put secret/redevops/aws-demo/config account_id=%s region=%s deploy_role_arn=%s agent_role_arn=%s readonly_role_arn=%s",
    data.aws_caller_identity.current.account_id, var.region,
    aws_iam_role.deployer.arn, aws_iam_role.agent.arn, aws_iam_role.readonly.arn,
  )
}
