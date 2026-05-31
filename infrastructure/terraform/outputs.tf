output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "Point your Route53 CNAME (api.<domain>) to this value."
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "backend_service_name"  { value = aws_ecs_service.backend.name }
output "frontend_service_name" { value = aws_ecs_service.frontend.name }

output "backend_log_group"  { value = aws_cloudwatch_log_group.backend.name }
output "frontend_log_group" { value = aws_cloudwatch_log_group.frontend.name }
