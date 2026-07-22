output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "region" {
  value = var.region
}

output "kubeconfig_command" {
  description = "Point kubectl/helm at the demo cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "ecr_registry" {
  value = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

output "ecr_repo_urls" {
  value = { for k, r in aws_ecr_repository.repo : k => r.repository_url }
}

data "aws_caller_identity" "current" {}
