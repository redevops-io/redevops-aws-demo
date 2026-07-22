# Self-managed observability on the demo EKS cluster — Helm-installed (NOT CloudWatch-managed).
# Applied AFTER the eks env exists; Sidekick + the security/compliance operators read these.
# kube-prometheus-stack = Prometheus + Grafana + Alertmanager; loki-stack = Loki + Promtail.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws        = { source = "hashicorp/aws", version = ">= 5.40" }
    helm       = { source = "hashicorp/helm", version = "~> 2.14" }
    kubernetes = { source = "hashicorp/kubernetes", version = ">= 2.30" }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}
variable "cluster_name" {
  type    = string
  default = "redevops-demo-demo"
}
variable "grafana_admin_password" {
  type      = string
  default   = "" # empty -> chart generates one; read it from the secret post-apply
  sensitive = true
}

provider "aws" { region = var.region }

data "aws_eks_cluster" "this" { name = var.cluster_name }
data "aws_eks_cluster_auth" "this" { name = var.cluster_name }

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

resource "kubernetes_namespace" "monitoring" {
  metadata { name = "monitoring" }
}

# Prometheus + Grafana + Alertmanager (small footprint for the demo).
resource "helm_release" "kube_prometheus_stack" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "62.7.0"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  timeout    = 900

  values = [yamlencode({
    grafana = {
      adminPassword             = var.grafana_admin_password != "" ? var.grafana_admin_password : null
      defaultDashboardsTimezone = "browser"
      resources                 = { requests = { cpu = "100m", memory = "128Mi" } }
    }
    prometheus = {
      prometheusSpec = {
        retention = "6h"
        resources = { requests = { cpu = "200m", memory = "512Mi" } }
        # scrape ServiceMonitors from all namespaces (edge-sentinel / operators expose metrics)
        serviceMonitorSelectorNilUsesHelmValues = false
        podMonitorSelectorNilUsesHelmValues     = false
        ruleSelectorNilUsesHelmValues           = false
      }
    }
    alertmanager = { alertmanagerSpec = { resources = { requests = { cpu = "50m", memory = "64Mi" } } } }
  })]
}

# Loki + Promtail (logs the incident loop reads).
resource "helm_release" "loki_stack" {
  name       = "loki-stack"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  version    = "2.10.2"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  timeout    = 900

  values = [yamlencode({
    loki     = { persistence = { enabled = false } }
    promtail = { enabled = true }
  })]
}
