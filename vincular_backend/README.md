# Vincular — Backend

API em **Django + Django REST Framework** com **PostgreSQL**.

Escopo: cadastro de crianças, salas e turmas, matrícula com capacidade (6), realocação de um dia,
presença com justificativa, ocorrências, importação/exportação de planilha, histórico e auditoria.

## Como rodar

```bash
docker compose up -d db                 # PostgreSQL (ou use um que você já tenha)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DJANGO_DEBUG=1                   # veja .env.example para as demais variáveis

python manage.py makemigrations core    # gera a migração inicial (primeira vez)
python manage.py migrate                # cria tabelas + gatilhos de regras e auditoria
python manage.py carregar_dias_turma    # A=1 (segunda) ... E=5 (sexta): CONFIRME a regra real
python manage.py createsuperuser        # o primeiro usuário já nasce administrador
python manage.py runserver
```

Testes automatizados (com o banco ligado): `python manage.py test`
Só os que não precisam de banco: `python -m unittest core.tests.test_planilhas core.tests.test_calendario`

## Autenticação

`POST /api/auth/login/` com `{"login": "...", "senha": "..."}` devolve um token.
Nas demais chamadas, envie o cabeçalho `Authorization: Token <token>`.

## Perfis

| Perfil | Pode |
|---|---|
| **administrador** | tudo: cadastros, matrículas, realocações, planilhas, auditoria; vê telefone |
| **monitor** | ver as crianças e turmas das suas salas (**sem telefone**), fazer a chamada, registrar ocorrências |

O monitor é ligado às turmas pela sala (`sala.profissional`).

## Endpoints principais

| Rota | Descrição |
|---|---|
| `/api/criancas/` | CRUD (admin escreve). Filtros: `?search=`, `?ativo=`, `?distrito=`, `?sem_turma=1` |
| `/api/criancas/{id}/historico/` | histórico completo da criança (admin) |
| `/api/salas/`, `/api/dias-turma/`, `/api/turmas/` | estrutura; a turma mostra `ocupadas` |
| `/api/matriculas/` | matrícula; encerre com `PATCH {"data_fim": "..."}`; `?ativa=1` |
| `/api/realocacoes/` | realocação de um dia (somente administrador) |
| `/api/turmas/{id}/chamada/?data=AAAA-MM-DD` | **GET** lista de chamada do dia (matriculados − realocados p/ fora + realocados p/ dentro) |
| `/api/turmas/{id}/chamada/` | **POST** `{"data": "...", "registros": [{"crianca": 1, "situacao": "presente"}]}` grava a chamada inteira |
| `/api/presencas/` | consulta/edição de presenças individuais |
| `/api/ocorrencias/` | comentários/ocorrências por criança |
| `/api/auditoria/` | log somente leitura (admin). Filtros: `tabela`, `registro_id`, `usuario_id`, `acao`, `data_hora__gte/lte` |
| `POST /api/importacao/criancas/` | planilha `.xlsx` no campo `arquivo`. Sem `?confirmar=1` só mostra a prévia |
| `GET /api/importacao/criancas/modelo/` | baixa a planilha-modelo |
| `GET /api/exportacao/criancas/` | exporta o cadastro (admin) |
| `GET /api/exportacao/presencas/?inicio=&fim=` | exporta a frequência do período |

Situações de presença: `presente`, `ausente`, `ausente_justificada` (justificativa obrigatória só nesta).

## Importação

Colunas: `nome`, `data_nascimento`, `codigo_v`, `responsavel`, `telefone`, `codigo_rm` (opcional), `distrito` (opcional).
O cabeçalho aceita acentos e variações ("Código V", "Nome do responsável"...). A chave é o **Código V**:
existente é atualizado, novo é criado. Células vazias não apagam dados já cadastrados.
Se houver qualquer erro, **nada é gravado** e a resposta lista as linhas com problema.

## Onde ficam as regras

As regras críticas estão no **banco** (`core/sql/regras_banco.sql`, reaplicado a cada `migrate`),
então valem para qualquer caminho de acesso (API, importação, shell):

- capacidade da turma, D1/D2 único por criança e conflito de horário na matrícula;
- realocação só por administrador, de turma em que a criança está matriculada, pode passar de 6;
- criança só entra na presença se estiver na lista de chamada do dia;
- Código V imutável;
- auditoria automática (quem, quando, antes/depois) em todas as tabelas de dados, imutável.

A API informa o usuário ao banco em cada requisição (`app.usuario_id`) — por isso `ATOMIC_REQUESTS = True`
não deve ser desligado.

## Dias da semana e atividades por criança

- A letra da turma é o dia da semana: **A = segunda, B = terça, C = quarta, D = quinta, E = sexta**
  (tabela `dia_turma`, preenchida por `python manage.py carregar_dias_turma`).
- Chamada, presença e realocação só aceitam datas que caem no dia da turma
  (na realocação, o dia da turma de **destino**).
- Cada criança faz **duas atividades em um dia**, ambas no **mesmo horário** (D1 ou D2), uma em cada tempo.
  A matrícula normal recusa outro dia da semana; a criança só aparece em outro dia por realocação.

## Observações

- A foto é enviada por `multipart/form-data` (campo `foto`) e salva em `media/`.
- A tabela `auditoria` bloqueia `UPDATE`, `DELETE` e `TRUNCATE`; por isso `manage.py flush` não funciona nela.
- Nada é apagado: criança desligada vira `ativo=false`; usuário, idem.
