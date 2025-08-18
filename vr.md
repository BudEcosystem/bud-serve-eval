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

/usr/local/lib/python3.10/site-packages/transformers/utils/hub.py:111: FutureWarning: Using `TRANSFORMERS_CACHE` is deprecated and will be removed in v5 of Transformers. Use `HF_HOME` instead.                                     │
│   warnings.warn(                                                                                                                                                                                                                     │
│ 08/17 09:49:14 - OpenCompass - INFO - Loading demo_gsm8k_chat_gen: /workspace/opencompass/configs/./datasets/demo/demo_gsm8k_chat_gen.py                                                                                             │
│ 08/17 09:49:14 - OpenCompass - INFO - Loading bud_model: /workspace/opencompass/configs/./models/bud_model.py                                                                                                                        │
│ 08/17 09:49:14 - OpenCompass - INFO - Loading example: /workspace/opencompass/configs/./summarizers/example.py                                                                                                                       │
│ 08/17 09:49:14 - OpenCompass - INFO - Current exp folder: /workspace/outputs/20250817_094914                                                                                                                                         │
│ 08/17 09:49:14 - OpenCompass - WARNING - SlurmRunner is not used, so the partition argument is ignored.                                                                                                                              │
│ 08/17 09:49:14 - OpenCompass - INFO - ./data/gsm8k/ does not exist!Start Download data automatically!If you have downloaded the data before,You can specific `COMPASS_DATA_CACHE` to avoid downloading~                              │
│ Downloading http://opencompass.oss-cn-shanghai.aliyuncs.com/datasets/data/gsm8k.zip to /root/.cache/opencompass/data/gsm8k.zip                                                                                                       │
│ 3.4/3.4 MB ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0:00:00                                                                                                                                                     │
│ Extracting /root/.cache/opencompass/data/gsm8k.zip to /root/.cache/opencompass/data                                                                                                                                                  │
│ Map:   0%|          | 0/7473 [00:00<?, ? examples/s]Map:   5%|▍         | 337/7473 [00:00<00:02, 2675.50 examples/s]Map:  10%|▉         | 723/7473 [00:00<00:02, 3133.66 examples/s]Map:  15%|█▍        | 1088/7473 [00:00<00:01, 32 │
│ Map:   0%|          | 0/1319 [00:00<?, ? examples/s]Map:  21%|██        | 272/1319 [00:00<00:00, 2601.76 examples/s]Map:  44%|████▎     | 576/









------


 OpenCompass Evaluation Results Structure

  The evaluation completed successfully with 42.19% accuracy on demo_gsm8k dataset. Here's the complete volume structure
  at /workspace/outputs/20250818_005107/:

  /workspace/outputs/20250818_005107/
  ├── configs/
  │   └── 20250818_005107_1.py          # Generated OpenCompass configuration
  ├── predictions/qwen3-4b/
  │   └── demo_gsm8k.json               # Model predictions (432KB)
  ├── results/qwen3-4b/
  │   └── demo_gsm8k.json               # Evaluation results (16KB)
  ├── summary/
  │   ├── summary_20250818_005107.csv   # Results CSV: accuracy=42.19%
  │   ├── summary_20250818_005107.md    # Markdown summary
  │   └── summary_20250818_005107.txt   # Text summary
  └── logs/
      ├── infer/qwen3-4b/
      │   └── demo_gsm8k.out            # Inference logs
      └── eval/qwen3-4b/
          └── demo_gsm8k.out            # Evaluation logs

  Key findings:
  - Results are organized by model name (qwen3-4b instead of request ID)
  - Predictions file contains full Q&A pairs with model reasoning
  - Results file contains scored evaluations
  - Summary provides final metrics in multiple formats
  - All model name fixes are working correctly

  The evaluation system is now fully functional and producing structured results.