# Remote state configuration
# Note: The S3 bucket and DynamoDB table must be created before this blocks can be initialized.
terraform {
  backend "s3" {
    bucket         = "togs-and-dogs-358604342897-us-east-1-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "togs-and-dogs-terraform-lock"
    # Note: dynamodb_table is used for locking. In TF 1.10+, S3 native 'use_lockfile' is preferred.
    profile = "usmissionhero-website-prod"
  }

  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
