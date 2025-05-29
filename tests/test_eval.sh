# Deploy job with volumes
curl -X POST "http://localhost:9081/evals/start" \
  -H "Content-Type: application/json" \
  -d '{
    "eval_request_id": "123e4567-e89b-12d3-a456-426614174000",
    "model_name": "gpt-4",
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1",
    "kubeconfig": "{...}",
    "source": "client_app",
    "source_topic": "budSimMessages"
  }'

# Check job status
# curl "http://localhost:9081/evals/status/eval-123e4567-e89b-12d3-a456-426614174000?kubeconfig={...}"

# # Cleanup resources
# curl -X DELETE "http://localhost:9081/evals/cleanup/eval-123e4567-e89b-12d3-a456-426614174000?kubeconfig={...}"