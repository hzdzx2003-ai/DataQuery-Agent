# Qwen Platform Notes

Verified against official Alibaba Cloud Model Studio documentation on 2026-09-22. Prices and free quotas can change; check the linked pages before running a paid evaluation.

## Region and endpoint

- Region: China (Beijing), `cn-beijing`.
- Standard OpenAI-compatible endpoint: `https://dashscope.aliyuncs.com/compatible-mode/v1`.
- A workspace-specific OpenAI-compatible endpoint can also be used: `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`.
- API keys, endpoints and model availability are region-specific and must not be mixed.

Sources: [region and endpoint guide](https://help.aliyun.com/zh/model-studio/regions/), [API key guide](https://help.aliyun.com/zh/model-studio/get-api-key).

## Planned models

| Purpose | Model | Verified notes |
|---|---|---|
| SQL generation and routing | `qwen3.7-plus` | Beijing alias points to `qwen3.7-plus-2026-05-26`; for requests up to 256K tokens, the listed original price is CNY 2/million input tokens and CNY 8/million output tokens, with a time-limited discount shown on the pricing page; 1 million free tokens are listed. |
| Embedding | `text-embedding-v4` | CNY 0.5/million input tokens in Beijing; 1 million free tokens for 90 days; dimensions 64–2048 with 1024 as default. |
| Rerank | `qwen3-rerank` | CNY 0.5/million input tokens in Beijing; 1 million free tokens for 90 days; no output-token charge. |

Sources: [official model pricing](https://help.aliyun.com/zh/model-studio/model-pricing), [embedding documentation](https://help.aliyun.com/zh/model-studio/embedding), [embedding and rerank model guide](https://help.aliyun.com/zh/model-studio/embedding-rerank-model).

## Safety and cost rules

- Store the key only in a local `.env`; never commit it or paste it into review files.
- Use a project-specific key with the minimum required model permissions when the console supports that configuration.
- Keep paid-evaluation runs bounded and log token usage.
- Do not state that the project will cost zero. Free quota eligibility and remaining balance must be confirmed in the user's console.

