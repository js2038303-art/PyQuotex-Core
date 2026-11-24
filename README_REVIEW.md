# PyQuotex — pacote revisado

## Instalação (Termux)

```bash
pkg update && pkg upgrade
pkg install python
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Coloque a pasta `pyquotex` no diretório do seu projeto e importe, por exemplo:

```python
from pyquotex.stable_api import Quotex
```

## Observações importantes da revisão

- A pasta de módulos HTTP foi normalizada para `http/`, que é o caminho importado por `api.py`.
- O tratamento de mensagens WebSocket foi ajustado para frames `str` e `bytes`, incluindo o prefixo de evento Socket.IO.
- Os parâmetros opcionais dos indicadores agora aceitam `None` usando os valores padrão.
- Esperas de candles/histórico não ficam presas em laço infinito quando a conexão cai.
- Corrigida a ordem de limpeza da resposta em `sell_option`, evitando perder uma resposta rápida.
- Consultas de payout para ativos inexistentes agora retornam `None`.
- O bloqueio de escrita do WebSocket é liberado mesmo se o envio lançar uma exceção.
- Arquivos de sessão/configuração recebem permissão restrita quando o sistema suporta `chmod`.

## Correções adicionais de sincronização WebSocket

- Implementados `subscribe_all_size` (`history/subscribe_all`) e `subscribe_Traders_mood` (`sentiment/subscribe`) na camada `api.py`, seguindo a implementação pública consultada do PyQuotex.
- Removida a chamada inexistente `refresh_settings`: `settings_apply` envia `settings/store` e a camada WebSocket já processa a resposta `settings/list`; agora a espera tem timeout de 10 segundos.
- Corrigida a resolução do código do ativo no fluxo de sentimento; removida a referência inexistente `traders_mood` e utilizado o cache existente `realtime_sentiment`.
- Corrigidos os caminhos de streaming de candles que consultavam caches inexistentes. A rotina agora usa o cache `realtime_candles` que já é alimentado pelo cliente WebSocket e possui timeout.
- `start_realtime_sentiment` agora solicita o stream de sentimento em vez de apenas iniciar candles.

## Limitações e validação

Os nomes dos eventos e payloads foram comparados com o código público do projeto PyQuotex, mas o protocolo é privado/não oficial e pode mudar sem aviso. A confirmação definitiva depende de uma sessão válida e de respostas reais do servidor. Não foi feita conexão com conta real nem teste de envio de ordens. Faça primeiro testes em conta DEMO; mantenha operações automáticas desabilitadas até confirmar autenticação, candles, sentimento e recebimento de configurações.
