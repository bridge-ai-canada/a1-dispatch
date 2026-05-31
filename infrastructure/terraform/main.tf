terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.55" }
  }
  # Recommended: configure a remote S3 backend with DynamoDB locking.
  # backend "s3" {
  #   bucket         = "a1fp-tfstate"
  #   key            = "envs/prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "a1fp-tfstate-lock"
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "a1-field-pro"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_availability_zones" "available" { state = "available" }

locals {
  name = "a1fp-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
}
