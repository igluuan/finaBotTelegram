# Documentação de Testes - FinaBotTelegram

Este documento descreve a estrutura de testes do projeto FinaBotTelegram, como executá-los e como adicionar novos testes.

## Estrutura de Testes

Os testes estão localizados no diretório `tests/` e seguem a mesma estrutura do código fonte:

main
```
tests/
├── bot/
│   ├── database/
│   │   └── test_crud.py       # Testes de integração com banco de dados (SQLite em memória)
│   ├── handlers/
│   │   ├── test_gasto.py      # Testes unitários para o handler de gastos
│   │   └── test_ganho.py      # Testes unitários para o handler de ganhos
│   └── services/
│       ├── test_ai_service.py # Testes unitários para o serviço de IA
│       └── test_parser.py     # Testes unitários para o parser de mensagens
└── conftest.py                # Configurações globais e fixtures (mocks)
```

## Tecnologias Utilizadas

- **pytest**: Framework de testes.
- **pytest-asyncio**: Suporte para testes assíncronos (coroutines).
- **pytest-mock**: Facilita a criação de mocks e stubs.
- **pytest-cov**: Relatórios de cobertura de código.
- **SQLAlchemy (SQLite in-memory)**: Banco de dados isolado para testes.

## Como Executar os Testes

1.  **Instale as dependências de desenvolvimento:**
    ```bash
    pip install -r requirements-dev.txt
    ```

2.  **Execute todos os testes:**
    ```bash
    python -m pytest tests/
    ```

3.  **Execute com relatório de cobertura:**
    ```bash
    python -m pytest --cov=finbot tests/
    ```

4.  **Execute com relatório detalhado (verbose):**
    ```bash
    python -m pytest -v tests/
    ```

## Descrição dos Testes

### Services (`test_parser.py`, `test_ai_service.py`)
- **Parser de Data**: Testa variações de entrada de data ("ontem", "dd/mm", etc.).
- **Parser Local**: Testa extração de valores e categorias via regex.
- **Parser IA**: Testa a integração com o serviço de IA (mockado), verificando sucesso, falha e fallback.
- **Detecção de Anomalia**: Testa a lógica de detecção de gastos incomuns.

### Database (`test_crud.py`)
- **CRUD Operations**: Testa criação, leitura, atualização e deleção de usuários, gastos, ganhos, parcelas e orçamentos.
- **Isolamento**: Usa um banco SQLite em memória que é limpo a cada teste para garantir independência.

### Handlers (`test_gasto.py`, `test_ganho.py`, `test_parcela.py`, `test_config.py`)
- **Fluxo de Conversa**: Simula o fluxo de conversa do Telegram (ConversationHandler).
- **Mocks**: `Update` e `Context` do Telegram são mockados para isolar a lógica do bot.
- **Cenários Cobertos**:
    - **Gastos e Ganhos**: Sucesso, validação de entrada, cancelamento.
    - **Parcelas**: Adição passo a passo, validação de cartão/valor, listagem, quitação e previsão do próximo mês.
    - **Configurações**: Cadastro inicial, definição de orçamento, remoção de gastos e exportação de CSV.

## Boas Práticas Adotadas

- **Arrange-Act-Assert**: Estrutura clara em cada teste.
- **Mocks e Stubs**: Dependências externas (Google Gemini, Telegram API) são mockadas para evitar chamadas reais e custos.
- **Isolamento**: Testes de banco de dados não afetam o ambiente de produção/desenvolvimento.
- **Cobertura de Exceções**: Testes para casos de erro (JSON inválido, API fora do ar, input malformado).
