POST /evals/start

{
  "eval_request_id": "123e4567-e89b-12d3-a456-426614174003",
  "engine": "opencompass",
  "model_name": "gpt-4",
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "datasets": ["gsm8k"]
}

1, Make sure we have the gsm8k dataset is available 
2, check the payloads are correctly getting created and log the payload when submitting the k8 job especially the cli arguments and related)
3, use k3s / kubectl to verify the job status and ensure it is running as expected.
4, 'eval_request_id' create a dynamic one
5, Current Custom Opencompass is available at `/home/ubuntu/opencompass-vr`
6, if you need latest information or anything related to opencompass then as deepwiki

ultrathink , this is high priority as it is core of the application 



dapr run --run-file ./app.yaml