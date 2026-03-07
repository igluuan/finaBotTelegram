# Linguagem natural enriquecida

Para agilizar o uso do bot no dia a dia, agora apresentamos opções explícitas de frases naturais que o assistente entende imediatamente.

### Exemplos recomendados
- `gastei 40 no Uber`
- `paguei aluguel hoje`
- `recebi salário`
- `quanto gastei essa semana`
- `parcelamento de 3x no cartão`
- `registra uma despesa em restaurantes`
- `mostra meu saldo do mês`
- `anota que comprei 120 em supermercado`

Essas frases são usadas:

1. No fallback do modelo (`ConversationResponse` de `conversation_manager`), que sugere até três das opções acima quando o LLM não entende a mensagem.
2. No `answer_natural` (quando o modelo não responde), para oferecer sugestões e deixar claro o tipo de comando natural que o bot lê.

Você pode escrever variações dessas frases — o parser/LLM entende valores, categorias e períodos. As respostas curtas com o Ollama também serão mais naturais, pois usamos esses exemplos nos prompts.
