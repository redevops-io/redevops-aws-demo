# AWS services & permissions the demo requires

Region: **us-east-1**. Two kinds of setup:
- **IAM** (free, do now) — the three roles Sidekick assumes. Already encoded in `infra/terraform/safety/roles.tf`.
- **Service enablement** (some cost — see the timing table) — turning services *on* (Bedrock model access, Inspector, Config, Security Hub, Macie, AgentCore). These are not IAM; they're account actions.

## IAM — the three assumed roles

### `redevops-demo-deployer` — provisioning (Terraform/EKS/ECR)
`ec2:*` (VPC · subnets · IGW/NAT · route tables · SGs · ENIs · EIPs · node EC2/EBS) · `eks:*` (cluster · nodegroups · addons · access entries) · `ecr:*` · `iam:*` (roles/policies · **OIDC provider for IRSA** · instance profiles · `PassRole`) · `autoscaling:*` · `application-autoscaling:*` · `elasticloadbalancing:*` · `elasticfilesystem:*` (EFS CSI) · `secretsmanager:*` · `kms:*` · `logs:*` · `ssm:*` · `cloudformation:*` · `s3:*` (TF state · artifacts · KB source · privacy dataset) · `acm:*` (TLS, optional) · `route53:*` (external-dns, optional) · `sts:GetCallerIdentity`

### `redevops-demo-agent` — AI runtime (Bedrock / AgentCore)
`bedrock:InvokeModel` · `InvokeModelWithResponseStream` · `Converse` · `ConverseStream` · `ListFoundationModels` · `GetFoundationModel` · `ListInferenceProfiles` · `Retrieve` · `RetrieveAndGenerate` (KB query) · `ApplyGuardrail` · `CreateGuardrail`/`GetGuardrail` · `bedrock-agent:*` (create/manage KBs · data sources · ingestion) · `bedrock-agent-runtime:*` · `bedrock-agentcore:*` (data plane) · `bedrock-agentcore-control:*` (Runtime · Gateway · Identity · Memory · Observability · Evaluations) · `aoss:*` **only if** OpenSearch Serverless is the KB vector store (see cost flag) · `s3:GetObject`/`ListBucket` (KB source)

### `redevops-demo-readonly` — monitor / security posture
`cloudwatch:Get*|List*|Describe*` · `logs:Get*|Describe*|FilterLogEvents|StartQuery|GetQueryResults` · `ce:Get*|List*|Describe*` (Cost Explorer) · `inspector2:List*|Get*|BatchGet*` (ECR image findings) · `config:Describe*|Get*|List*|SelectResourceConfig` · `macie2:List*|Get*|Describe*` · `securityhub:Get*|List*|Describe*` · `eks:Describe*|List*` · `ecr:Describe*|List*|BatchGetImage|GetDownloadUrlForLayer|GetAuthorizationToken`

> Using the existing account? Point `-var bootstrap_principal_arn=…` at your bootstrap user (a user with **only** `sts:AssumeRole` on the three role ARNs) and `terraform apply infra/terraform/safety/`. Or, for a quick start, attach the three permission sets directly to one user — but role assumption is the intended boundary.

## Service enablement (not IAM)

| Service | Why | How | Cost |
|---|---|---|---|
| **Bedrock model access** | model plane (Claude/Nova/Titan…) | Bedrock console → *Model access* → request per model | free to enable; pay per token |
| **Bedrock AgentCore** | host Sidekick/Strands agents | confirm available in us-east-1; enable | pay per use |
| **Amazon Inspector** | ECR image scanning (edge-sentinel) | Inspector console → activate (ECR scanning) | per-image scan (cheap) |
| **AWS Config** | compliance posture (Agentic Compliance) | enable recorder + delivery channel (S3) | per config item (adds up) |
| **Security Hub** | aggregate Inspector/Config findings | enable | per finding/check |
| **Amazon Macie** | PII discovery in S3 (Agentic Privacy) | enable + a discovery job on the **tiny seeded** bucket | per GB + per bucket (keep dataset tiny) |
| **KB vector store** | Bedrock Knowledge Bases needs one | **prefer S3 Vectors or Aurora Serverless v2 pgvector** | ⚠ **avoid OpenSearch Serverless** — ~$700/mo OCU floor |

## Do-now vs hold-until-credits (while your application is under review)

**Do now (free / negligible):**
- Apply the **IAM** (all three roles) — free.
- Request **Bedrock model access** — free until you invoke.
- Activate **Amazon Inspector** — cost only when images are scanned.
- Create the **bootstrap user** (`sts:AssumeRole` only) + write Vault `bootstrap`/`config`.

**Hold until credits land (ongoing cost):**
- The **EKS cluster** itself — control plane ~$0.10/hr (~$73/mo) + node EC2/EBS. This is the main burn; stand it up only for real runs/recording.
- **AWS Config** recorder, **Security Hub**, **Macie** discovery jobs — enable right before the compliance/privacy phase, against the seeded targets, then disable.
- **OpenSearch Serverless** — don't; use S3 Vectors / Aurora pgvector for the KB.

The out-of-band Budgets kill-switch (`infra/terraform/safety/`) should be applied **before** the first EKS stand-up so the cap is armed the moment anything costs money.
