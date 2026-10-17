# InBody para Home Assistant

Integração customizada (HACS) que traz a última medição da sua balança **InBody Dial H30** para o Home Assistant: peso, IMC, % de gordura, massa muscular esquelética, massa de gordura e água corporal total.

> **Aviso:** o InBody não tem API pública para uso pessoal. Esta integração usa a API móvel do app InBody, descoberta por engenharia reversa por [rwestergren/inbody-api-mcp](https://github.com/rwestergren/inbody-api-mcp) (MIT). Ela é **não oficial** e pode parar de funcionar se o InBody mudar o app ou os servidores. Use por sua conta e risco.

## Como funciona

A balança sincroniza a medição com a nuvem do InBody (via Wi-Fi/app). O Home Assistant faz login com a sua conta, na nuvem, e consulta a última medição a cada 30 minutos (configurável). Não há comunicação direta com a balança.

Consequência: o dado só aparece no HA **depois** que a medição chegou ao app do InBody.

## Instalação (HACS)

1. Publique esta pasta como um repositório no GitHub (os arquivos `hacs.json` e `custom_components/` precisam ficar na raiz).
2. No HA: **HACS → ⋮ → Repositórios personalizados** → cole `https://github.com/jacardbr/ha-inbody`, categoria **Integração** → Adicionar.
3. Procure por **HA InBody** no HACS e baixe.
4. **Reinicie o Home Assistant.** Em Docker: `docker restart <nome-do-container>`. Não é preciso mexer em volumes: o HACS grava em `/config/custom_components/ha_inbody`, que já está no volume do seu `/config`.
5. **Configurações → Dispositivos e serviços → Adicionar integração → HA InBody**.

Instalação manual (sem HACS): copie `custom_components/ha_inbody` para `<seu /config>/custom_components/ha_inbody` e reinicie.

## Configuração

| Campo | O que colocar |
|---|---|
| ID de login | O **telefone** usado no cadastro do app InBody, só dígitos, sem código do país nem `+`. E-mail não funciona. |
| Senha | A senha do app InBody. |
| País | Código ISO de 2 letras (`BR`, `US`…). O padrão é `BR`. |
| Importar medições antigas após a configuração | Marcado por padrão. Busca todo o histórico uma única vez, em segundo plano (veja [Importar o histórico](#importar-o-histórico)). |

Depois de configurada, clique em **Configurar** na integração: aparece um menu com **Alterar intervalo de atualização** (5 a 1440 min) e **Importar histórico agora**.

## Entidades

| Entidade | Unidade |
|---|---|
| Peso | kg |
| IMC | kg/m² |
| Percentual de gordura | % |
| Massa muscular esquelética | kg |
| Massa de gordura | kg |
| Água corporal total | kg |
| Última medição | data/hora |

A entidade **Última medição** também traz, como atributos `bca` e `mfa`, **todos** os campos que a API devolveu. Qualquer métrica sem sensor próprio (gordura visceral, TMB, água intra/extracelular etc.) pode ser lida de lá com um template, por exemplo:

```yaml
template:
  - sensor:
      - name: "InBody campo exemplo"
        state: "{{ state_attr('sensor.inbody_ultima_medicao', 'bca')['NOME_DO_CAMPO'] }}"
```

(Ajuste o `entity_id` ao que aparece no seu HA.) Para descobrir os nomes dos campos: **Dispositivos e serviços → InBody → ⋮ → Baixar diagnóstico** (a senha e o telefone são ocultados).

## Importar o histórico

A integração só enxerga a medição mais recente a partir do momento em que é instalada. Para trazer **todas as medições antigas** da sua conta InBody, deixe marcada a opção **Importar medições antigas após a configuração** ao adicionar a integração: a importação roda uma única vez, em segundo plano, e a opção se desmarca sozinha quando termina com sucesso. Se falhar (por exemplo, sem internet), ela tenta de novo na próxima vez que a integração carregar.

Para importar a qualquer momento: em **Configurações → Dispositivos e serviços → HA InBody → Configurar**, escolha **Importar histórico agora** e confirme. Ao terminar, o HA mostra quantas medições foram encontradas e quantos pontos foram gravados.

Outra forma, útil para automações, é a ação `ha_inbody.import_history`:

1. **Ferramentas do desenvolvedor → Ações**.
2. Escolha **HA InBody: Importar histórico** (`ha_inbody.import_history`).
3. Opcional: escolha a conta; vazio importa todas as contas configuradas.
4. **Executar ação**. A resposta mostra quantas medições foram encontradas e quantos pontos foram gravados por sensor.

O que ela faz: busca todas as medições na nuvem e grava **estatísticas de longo prazo (por hora)** nos sensores de peso, IMC, % de gordura, massa muscular, massa de gordura e água corporal. Os pontos antigos aparecem nos gráficos de estatísticas, por exemplo:

```yaml
type: statistics-graph
title: Peso
entities:
  - sensor.inbody_peso   # ajuste ao entity_id do seu HA
stat_types:
  - mean
period: month
days_to_show: 730
```

Detalhes:

- Os sensores precisam já existir, ou seja, rode a ação depois de configurar a integração.
- É seguro executar de novo: as mesmas horas são sobrescritas com os mesmos valores.
- Se houver duas medições na mesma hora, vale a última.
- As medições antigas aparecem nos **gráficos de estatísticas**, não no cartão **Histórico** (que mostra estados registrados, e não estatísticas).
- A importação usa a API de estatísticas do recorder, que mudou em versões recentes do HA. Se a ação reclamar da versão, atualize o Home Assistant.

## Problemas comuns

- **"Falha no login"**: confira se está usando o telefone (não o e-mail), só dígitos.
- **"O InBody não publica um servidor de API para esse código de país"**: o país não está na tabela de hosts do InBody; tente o país onde o app foi cadastrado.
- **Sensores "desconhecido"**: a conta ainda não tem nenhuma medição na nuvem. Meça e confirme que ela aparece no app.
- **Pediu para autenticar de novo**: a senha mudou ou o InBody invalidou o login; o HA mostra o aviso de reautenticação.
- Logs: ative `logger: logs: custom_components.ha_inbody: debug` no `configuration.yaml`.

## Privacidade

Telefone e senha ficam guardados no armazenamento do Home Assistant (`/config/.storage`), em texto simples, como acontece com a maioria das integrações em nuvem. Proteja o backup do seu `/config`.

## Desenvolvimento

Testes da camada de API (só biblioteca padrão):

```bash
python3 -m unittest discover -s tests -v
```

Créditos: protocolo da API por [rwestergren/inbody-api-mcp](https://github.com/rwestergren/inbody-api-mcp).
