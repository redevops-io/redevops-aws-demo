data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  name = "${var.project_name}-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
}

# ---- VPC (single NAT to keep the demo cheap) ----
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, i)]
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, i + 100)]

  enable_nat_gateway   = true
  single_nat_gateway   = true # one NAT (not per-AZ) — cheaper for a demo
  enable_dns_hostnames = true

  # tags the load-balancer controller + EKS expect for subnet discovery
  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }
}

# ---- EKS (one small managed node group) ----
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.name
  cluster_version = var.kubernetes_version

  vpc_id                               = module.vpc.vpc_id
  subnet_ids                           = module.vpc.private_subnets
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = var.public_access_cidrs

  # let the applying identity administer the cluster (kubectl / helm from the operator)
  enable_cluster_creator_admin_permissions = true

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
    # aws-ebs-csi-driver intentionally omitted: nothing in the demo uses persistent volumes
    # (Prometheus/Grafana/Loki all run on emptyDir). It also needs an IRSA role and commonly
    # hangs "creating" without one. Re-add with a service_account_role_arn if you need dynamic EBS.
  }

  eks_managed_node_groups = {
    demo = {
      name           = "demo-nodes"
      instance_types = var.node_instance_types
      capacity_type  = var.use_spot ? "SPOT" : "ON_DEMAND"
      ami_type       = "AL2023_x86_64_STANDARD"
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = var.node_disk_size
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }
      labels = { role = "demo" }
    }
  }
}

# ---- ECR repos (scan-on-push so edge-sentinel + Inspector have findings) ----
resource "aws_ecr_repository" "repo" {
  for_each             = toset(var.ecr_repos)
  name                 = "${local.name}/${each.value}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # demo: let terraform destroy clean images too

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "repo" {
  for_each   = aws_ecr_repository.repo
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}
