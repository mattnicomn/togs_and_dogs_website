# Default provider — Workload account (usmissionhero-website-prod)
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile_workload

  default_tags {
    tags = local.common_tags
  }
}

# ACM provider — CloudFront requires certificates in us-east-1
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile_workload

  default_tags {
    tags = local.common_tags
  }
}

# DNS provider — Route 53 Hosted Zone resides in the sandbox/DNS account
provider "aws" {
  alias   = "dns"
  region  = "us-east-1" # Route 53 is global but specific region is required for provider
  profile = var.aws_profile_dns

  default_tags {
    tags = local.common_tags
  }
}
