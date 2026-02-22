# Cookbook: Multi-framework Integration

Use `tooli-export` to generate wrappers for common agent frameworks.

## OpenAI Agents SDK

```bash
tooli-export openai app_module:app --mode import > tools_openai.py
```

## LangChain

```bash
tooli-export langchain app_module:app --mode import > tools_langchain.py
```

## Google ADK

```bash
tooli-export adk app_module:app > agent.yaml
```

## Python wrapper module

```bash
tooli-export python app_module:app > client.py
```
