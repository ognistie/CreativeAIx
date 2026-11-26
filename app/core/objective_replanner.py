"""O modelo escolhe uma opção enumerada. A execução nunca recebe parâmetros do modelo.

Vale para qualquer provedor (Anthropic, DeepSeek, Ollama...): falha de transporte vira RuntimeError e uma resposta
fora do formato é recusada inteira pelo RunContext (nunca uma estratégia inventada ou parâmetro do modelo).
"""
import json

from anthropic import APIError

from core.model_provider import ProviderError


def choose_read_strategy(client, model, observation, choices):
    schema = {"type": "object", "properties": {
        "strategy": {"type": "string", "enum": [*choices, "stop"]}},
        "required": ["strategy"], "additionalProperties": False}
    try:
        response = client.message(
            model, "Escolha uma estratégia de leitura a partir das evidências. "
            "Se a evidência for insuficiente, escolha stop.",
            json.dumps({"objective": "verificar trecho literal no documento original",
                        "observation": observation, "choices": choices}),
            max_tokens=120, agent="MAESTRO", json_schema=schema)
    except (APIError, ProviderError) as error:
        raise RuntimeError("Transporte do replanejador indisponível.") from error
    # Validação da forma fica no RunContext: chave extra ou opção fora da lista recusa a resposta inteira
    return json.loads(response)
