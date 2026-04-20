output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.frontend.domain_name
  description = "The domain name of the CloudFront distribution"
}

output "acm_certificate_validation_options" {
  value       = aws_acm_certificate.cert.domain_validation_options
  description = "DNS validation options for the ACM certificate"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.frontend.id
  description = "The name of the S3 bucket for frontend assets"
}
