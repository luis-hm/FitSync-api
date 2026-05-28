# AGENTE.md — Contexto do Projeto: Sistema Personal & Aluno

**Este arquivo é o documento vivo do projeto.** Toda decisão de arquitetura, banco de dados, API e frontend deve ser lida e evoluída a partir daqui. Ao iniciar qualquer tarefa, referencie este arquivo como contexto base.

---

## 1\. Visão Geral do Projeto

**Nome:** Sistema Personal & Aluno **Objetivo:** Plataforma web para administradores, personal trainers e alunos, com gestão de usuários, alunos, fichas de treino, templates, avaliações físicas por método e acompanhamento gráfico de evolução. **Fase atual:** 🟠 Implementação — Stack definida, iniciando Fase 1 (Fundação)

### Stack definida

| Camada | Tecnologia | Observação |
| :---- | :---- | :---- |
| Frontend | Next.js (App Router) \+ TypeScript | Rewrite `/api/*` → backend |
| Backend | Django 6 \+ DRF \+ Daphne/ASGI | ASGI desde o início para suportar WS futuro |
| Banco | PostgreSQL 16 | Obrigatório — window functions e CTEs das queries de evolução |
| Auth | JWT access em JSON \+ refresh em cookie HttpOnly | Endpoint base `/api/auth/`, sem localStorage para refresh |
| Async | Futuro: Celery worker \+ beat | Fora do ambiente atual até o domínio exigir processamento assíncrono |
| Cache / broker | Futuro: Redis | Fora do ambiente atual |
| Dev orchestration | Makefile \+ Procfile/Honcho | `make dev` sobe banco, migra e inicia API |
| Containers | Docker Compose | PostgreSQL local em container; Django roda local via Poetry |
| Dependências Python | Poetry | `pyproject.toml` \+ `poetry.lock` versionados |

---

## 2\. Módulos do Sistema

sistema-personal/

├── backend/                   → projeto Django

│   ├── config/                → settings, urls, asgi, wsgi

│   └── apps/

│       ├── core/              → middleware, mixins, exceções, logging

│       ├── accounts/          → usuario, perfis, aluno, JWT auth

│       ├── workouts/          → exercicio, treino, item\_treino

│       └── assessments/       → avaliacao \+ motor J\&P \+ relatórios

└── frontend/                  → projeto Next.js

    └── src/

        ├── app/               → páginas (App Router)

        ├── components/

        │   ├── global/        → layout, navbar, sidebar

        │   └── features/      → workouts/, assessments/

        ├── lib/               → apiClient.ts, apiService.ts

        ├── types/             → api/, entities/

        └── utils/mappers/     → response API → entidade tipada

---

## 3\. Modelagem do Banco de Dados

### 3.1 Módulo: `accounts` — Gestão de Usuários

#### Tabela: `usuario`

Tabela base para autenticação. Um único registro representa `ADMIN`, `PERSONAL` ou `ALUNO`. No Django, estende `AbstractBaseUser` para usar `email` como campo de login.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | UUID gerado automaticamente |
| `nome` | String | Nome completo do usuário |
| `email` | String ÚNICO | Email utilizado para login |
| `senha` | String | Hash gerenciado pelo Django (PBKDF2 padrão) |
| `tipo` | Enum (`ADMIN`, `PERSONAL`, `ALUNO`) | Papel de produto usado pelo login, permissões e frontend |
| `is_active` | Boolean | Controle de ativação do usuário |
| `is_staff` | Boolean | Acesso ao Django Admin quando aplicável |
| `is_superuser` | Boolean | Permissão total do Django para administradores internos |
| `data_criacao` | DateTime | Auto preenchido em `created_at` |

**Nota de implementação Django:** Usar `AbstractBaseUser` \+ `BaseUserManager` customizado com `email` como `USERNAME_FIELD`. Adicionar `AUTH_USER_MODEL = 'accounts.Usuario'` no `settings.py`. O cadastro público pode criar apenas `PERSONAL` e `ALUNO`; `ADMIN` nasce por superuser/admin interno.

#### Tabela: `aluno`

Perfil estendido do usuário aluno, com dados específicos de saúde e objetivo.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `usuario_id` | FK → usuario | OneToOneField com `usuario` |
| `personal_id` | FK → usuario | ForeignKey para o personal responsável (`tipo=PERSONAL`) |
| `data_nascimento` | Date | Usado para calcular idade nas fórmulas de BF |
| `sexo` | Enum ('M','F') | Obrigatório para Jackson & Pollock — imutável após cadastro |
| `objetivo_principal` | String | Ex: "Hipertrofia", "Emagrecimento", "Condicionamento" |
| `observacoes_medicas` | Text | Ex: "Hérnia de disco", "Asma", "Hipertensão" |

**Validação de imutabilidade de `sexo`:** O serializer de PATCH deve verificar se o aluno já possui avaliações. Se sim, retorna HTTP 400 com mensagem explicativa — nunca altera `sexo` silenciosamente.

**Relacionamentos do módulo `accounts`:**

usuario (1) ── (1) aluno   \[usuario\_id — OneToOneField\]

usuario PERSONAL (1) ── (N) aluno   \[personal\_id — ForeignKey\]

---

### 3.2 Módulo: `workouts` — Catálogo e Fichas de Treino

#### Tabela: `exercicio`

Catálogo global. Qualquer personal pode usar qualquer exercício — não há vínculo de ownership.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `nome` | String | Ex: "Supino Reto", "Agachamento Livre" |
| `grupo_muscular` | String | Ex: "Peito", "Costas", "Perna", "Ombro" |
| `url_animacao` | String / URL | Link para gif ou vídeo de execução (opcional) |
| `instrucoes_gerais` | Text | Detalhes de postura, execução e dicas de segurança |
| `ativo` | Boolean | Arquivamento lógico do exercício |

#### Tabela: `treino_template`

Modelo reutilizável criado por um personal. Serve como base para montar fichas reais de alunos sem acoplar alterações futuras.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `personal_id` | FK → usuario | Personal dono do template (`tipo=PERSONAL`) |
| `titulo` | String | Ex: "Hipertrofia - Iniciante" |
| `descricao` | Text | Observações gerais do template |
| `ativo` | Boolean | Permite arquivar templates sem apagar histórico |
| `data_criacao` | DateTime | Data de criação |

#### Tabela: `item_treino_template`

Itens do template com exercícios e parâmetros prescritos.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `template_id` | FK → treino_template | Template ao qual pertence |
| `exercicio_id` | FK → exercicio | Exercício do catálogo global |
| `series` | Integer | Ex: 4 |
| `repeticoes` | String | String por flexibilidade — aceita "10 a 12" ou "Falha" |
| `descanso_segundos` | Integer | Ex: 60 |
| `ordem_execucao` | Integer | Obrigatório — define sequência na tela |

#### Tabela: `treino`

Ficha real criada pelo personal para um aluno específico. Pode nascer do zero ou a partir de um template; ao aplicar template, os itens são copiados e ficam independentes.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `aluno_id` | FK → aluno | ForeignKey com `aluno` |
| `template_origem_id` | FK → treino_template | Opcional; referência histórica ao template usado |
| `titulo` | String | Ex: "Treino A \- Peito e Tríceps" |
| `dia_da_semana` | Enum | Opcional — `SEGUNDA`, `TERCA`, `QUARTA`, `QUINTA`, `SEXTA`, `SABADO`, `DOMINGO` |
| `data_inicio` | Date | Data de início da vigência |
| `data_vencimento` | Date | Data prevista para troca da ficha |
| `ativo` | Boolean | Somente uma ficha `ativo=True` por aluno por vez |

**Validação de ficha ativa:** Ao ativar um `treino`, o backend deve setar `ativo=False` em todos os outros treinos daquele aluno via `Treino.objects.filter(aluno=aluno).exclude(pk=instance.pk).update(ativo=False)`. Implementar no serializer ou em um signal `pre_save`.

#### Tabela: `item_treino`

Junção N:M entre `treino` e `exercicio` com detalhes de execução.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `treino_id` | FK → treino | ForeignKey |
| `exercicio_id` | FK → exercicio | ForeignKey |
| `series` | Integer | Ex: 4 |
| `repeticoes` | String | String por flexibilidade — aceita "10 a 12" ou "Falha" |
| `descanso_segundos` | Integer | Ex: 60 |
| `ordem_execucao` | Integer | Obrigatório — define sequência na tela do Next.js |

**Relacionamentos do módulo `workouts`:**

usuario PERSONAL (1) ── (N) treino_template \[personal\_id\]

treino_template (1) ── (N) item_treino_template \[template\_id\]

aluno     (1) ── (N) treino       \[aluno\_id\]

treino    (1) ── (N) item\_treino  \[treino\_id\]

exercicio (1) ── (N) item\_treino  \[exercicio\_id\]

---

### 3.3 Módulo: `assessments` — Acompanhamento e Evolução

Módulo com regra de negócio complexa. Usa padrão avançado com `application/use_cases.py` separado do layer de API.

#### Tabela: `avaliacao`

Registro-raiz de uma sessão. Contém o método escolhido, inputs básicos e todos os campos **calculados** pelo backend quando aplicável.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `aluno_id` | FK → aluno | ForeignKey |
| `personal_id` | FK → usuario | Personal que registrou a avaliação |
| `metodo` | Enum | `DOBRAS`, `BIOIMPEDANCIA`, `CIRCUNFERENCIAS` ou `COMBINADO` |
| `data_avaliacao` | Date | Data do registro das medidas |
| `peso_kg` | Decimal(5,2) | Input |
| `altura_cm` | Integer | Input |
| `densidade_corporal` | Decimal(6,5) | Calculado — Jackson & Pollock |
| `percentual_gordura` | Decimal(5,2) | Calculado — equação de Siri |
| `massa_gorda_kg` | Decimal(5,2) | Calculado |
| `massa_magra_kg` | Decimal(5,2) | Calculado |
| `rcq` | Decimal(4,2) | Calculado — cintura / quadril |
| `feedback_personal` | Text | Notas do personal (input opcional) |
| `ativo` | Boolean | Arquivamento lógico da avaliação |

#### Tabela: `avaliacao_dobras`

7 pontos do protocolo Jackson & Pollock medidos com adipômetro (mm).

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `avaliacao_id` | FK → avaliacao | OneToOneField |
| `peitoral_mm` | Decimal(5,2) | Diagonal entre axila e mamilo |
| `axilar_media_mm` | Decimal(5,2) | Vertical na linha da axila, altura do esterno |
| `triceps_mm` | Decimal(5,2) | Vertical na parte posterior do braço |
| `subescapular_mm` | Decimal(5,2) | Diagonal abaixo da escápula |
| `abdominal_mm` | Decimal(5,2) | Vertical ao lado do umbigo |
| `supra_iliaca_mm` | Decimal(5,2) | Diagonal acima do osso do quadril |
| `coxa_mm` | Decimal(5,2) | Vertical na parte anterior da coxa |
| `soma_7_dobras` | Decimal(6,2) | Σ7DC — calculado pelo backend |

#### Tabela: `avaliacao_bioimpedancia`

Dados obtidos em balanças ou equipamentos de bioimpedância. Os valores informados ficam no histórico, sem sobrescrever perfil do aluno.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `avaliacao_id` | FK → avaliacao | OneToOneField |
| `percentual_gordura` | Decimal(5,2) | Valor informado pelo equipamento |
| `massa_gorda_kg` | Decimal(5,2) | Opcional |
| `massa_magra_kg` | Decimal(5,2) | Opcional |
| `massa_muscular_kg` | Decimal(5,2) | Opcional |
| `agua_corporal_percentual` | Decimal(5,2) | Opcional |
| `gordura_visceral` | Decimal(5,2) | Opcional |
| `taxa_metabolica_basal` | Integer | Opcional |

#### Tabela: `avaliacao_circunferencias`

10 medidas de circunferência (cm) com fita métrica.

| Atributo | Tipo / Chave | Descrição |
| :---- | :---- | :---- |
| `id` | PK (UUID) | Identificador único |
| `avaliacao_id` | FK → avaliacao | OneToOneField |
| `pescoco_cm` | Decimal(5,2) |  |
| `torax_cm` | Decimal(5,2) |  |
| `cintura_cm` | Decimal(5,2) | Ponto mais estreito — usado no RCQ |
| `abdome_cm` | Decimal(5,2) | Linha do umbigo |
| `quadril_cm` | Decimal(5,2) | Usado no RCQ |
| `braco_relaxado_cm` | Decimal(5,2) |  |
| `braco_contraido_cm` | Decimal(5,2) | Pico bíceps |
| `antebraco_cm` | Decimal(5,2) |  |
| `coxa_cm` | Decimal(5,2) |  |
| `panturrilha_cm` | Decimal(5,2) |  |

**Relacionamentos do módulo `assessments`:**

aluno        (1) ── (N) avaliacao                \[aluno\_id\]

usuario PERSONAL (1) ── (N) avaliacao             \[personal\_id\]

avaliacao    (1) ── (1) avaliacao\_dobras          \[avaliacao\_id — OneToOneField\]

avaliacao    (1) ── (1) avaliacao\_bioimpedancia   \[avaliacao\_id — OneToOneField\]

avaliacao    (1) ── (1) avaliacao\_circunferencias \[avaliacao\_id — OneToOneField\]

---

## 4\. Diagrama de Relacionamentos (Visão Geral)

┌──────────────┐       ┌──────────────────┐

│   usuario    │ 1   1 │      aluno       │

│──────────────│───────│──────────────────│

│ id (PK/UUID) │       │ id (PK/UUID)     │

│ nome         │       │ usuario\_id FK    │

│ email        │       │ personal\_id FK   │

│ senha (hash) │       │ data\_nascimento  │

│ is\_personal  │       │ sexo (M/F)       │

│ data\_criacao │       │ objetivo         │

└──────────────┘       │ obs\_medicas      │

       ▲ personal\_id   └────────┬─────────┘

       └────────────────────────┘

                       │ 1

              ┌────────┴──────────────────────────┐

              │ N                                 │ N

              ▼                                   ▼

     ┌──────────────┐                   ┌──────────────────┐

     │    treino    │──N item\_treino N──│    avaliacao     │

     │──────────────│   exercicio       │──────────────────│

     │ id (UUID)    │                   │ id (UUID)        │

     │ aluno\_id FK  │                   │ aluno\_id FK      │

     │ titulo       │                   │ peso\_kg          │

     │ dia\_semana   │                   │ altura\_cm        │

     │ data\_inicio  │                   │ densidade\_corp.\* │

     │ data\_vencim. │                   │ perc\_gordura \*   │

     │ ativo        │                   │ massa\_gorda\_kg \* │

     └──────────────┘                   │ massa\_magra\_kg \* │

                                        │ rcq \*            │

                                        │ feedback         │

                                        └────────┬─────────┘

                                                 │ 1

                                   ┌─────────────┴──────────────┐

                                   │ 1                          │ 1

                                   ▼                            ▼

                        ┌──────────────────┐     ┌──────────────────────────┐

                        │ avaliacao\_dobras │     │ avaliacao\_circunferencias│

                        │──────────────────│     │──────────────────────────│

                        │ peitoral\_mm      │     │ pescoco\_cm               │

                        │ axilar\_media\_mm  │     │ torax\_cm                 │

                        │ triceps\_mm       │     │ cintura\_cm               │

                        │ subescapular\_mm  │     │ abdome\_cm                │

                        │ abdominal\_mm     │     │ quadril\_cm               │

                        │ supra\_iliaca\_mm  │     │ braco\_relaxado\_cm        │

                        │ coxa\_mm          │     │ braco\_contraido\_cm       │

                        │ soma\_7\_dobras \*  │     │ antebraco\_cm             │

                        └──────────────────┘     │ coxa\_cm                  │

                                                 │ panturrilha\_cm           │

                                                 └──────────────────────────┘

\* \= campos calculados pelo backend

---

## 5\. Regras de Negócio

1. **Autenticação única por papel:** `tipo` em `usuario` distingue `ADMIN`, `PERSONAL` e `ALUNO`; a interface pós-login muda com base nesse campo.  
2. **Admin interno:** `ADMIN` não é personal nem aluno; pode gerir usuários, personais, alunos e vínculos no painel administrativo.  
3. **Vínculo aluno-personal:** Todo aluno deve ter um `personal_id` válido apontando para usuário `tipo=PERSONAL` — não existe aluno sem personal.  
4. **Escopo de acesso:** Personal só acessa alunos, treinos e avaliações vinculados a ele; aluno só acessa os próprios treinos e avaliações.  
5. **Ficha ativa:** Um aluno pode ter múltiplas fichas, mas apenas uma com `ativo=True` por vez. Ao ativar uma nova, as anteriores são desativadas automaticamente no backend.  
6. **Templates independentes:** Ao aplicar um `treino_template` a um aluno, o backend copia seus itens para uma ficha real; alterações futuras no template não alteram treinos já aplicados.  
7. **Histórico de avaliações:** Avaliações nunca são deletadas — soft delete se necessário. O histórico completo é essencial para as window functions.  
8. **Medidas no histórico:** Medidas corporais, dobras e bioimpedância pertencem às avaliações, não ao cadastro do aluno, para preservar evolução/regressão ao longo do tempo.  
9. **Catálogo de exercícios global:** Qualquer personal pode usar qualquer exercício — sem ownership.  
10. **`ordem_execucao` obrigatório:** Necessário para renderização correta na tela do Next.js.  
11. **BF por método:** Em dobras, o backend calcula BF a partir das 7 dobras \+ sexo \+ idade; em bioimpedância, os valores informados pelo equipamento ficam registrados como histórico.  
12. **RCQ com classificação OMS:** Risco elevado quando RCQ \> 0.90 (homens) ou \> 0.85 (mulheres). O relatório sinaliza visualmente.  
13. **`sexo` imutável após avaliações:** O serializer bloqueia PATCH em `sexo` se já existirem avaliações associadas ao aluno.
14. **API de domínio via ViewSets:** CRUDs do MVP usam `ViewSet` \+ routers, paginação `PageNumberPagination` com `PAGE_SIZE=20` e filtros manuais por query params.
15. **Arquivamento lógico:** Recursos principais usam `ativo=False` em vez de DELETE físico; listas exibem ativos por padrão e aceitam filtro `?ativo=false`.
16. **Payloads aninhados:** Templates, treinos e avaliações são criados/atualizados com itens/medidas aninhados em transação atômica.

---

## 6\. Queries SQL Avançadas (trabalho acadêmico — PostgreSQL)

### Evolução de peso e composição corporal (Window Function)

SELECT

  aluno\_id,

  data\_avaliacao,

  peso\_kg,

  percentual\_gordura,

  massa\_magra\_kg,

  LAG(peso\_kg)            OVER (PARTITION BY aluno\_id ORDER BY data\_avaliacao) AS peso\_anterior,

  LAG(percentual\_gordura) OVER (PARTITION BY aluno\_id ORDER BY data\_avaliacao) AS bf\_anterior,

  peso\_kg \- LAG(peso\_kg)  OVER (PARTITION BY aluno\_id ORDER BY data\_avaliacao) AS variacao\_peso\_kg,

  percentual\_gordura \- LAG(percentual\_gordura) OVER (PARTITION BY aluno\_id ORDER BY data\_avaliacao) AS variacao\_bf

FROM avaliacao;

### Ranking de alunos por perda de gordura (CTE \+ Window Function)

WITH evolucao AS (

  SELECT

    aluno\_id,

    FIRST\_VALUE(percentual\_gordura) OVER (PARTITION BY aluno\_id ORDER BY data\_avaliacao

      ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS bf\_inicial,

    LAST\_VALUE(percentual\_gordura)  OVER (PARTITION BY aluno\_id ORDER BY data\_avaliacao

      ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS bf\_atual

  FROM avaliacao

)

SELECT DISTINCT

  aluno\_id,

  bf\_inicial,

  bf\_atual,

  ROUND(((bf\_inicial \- bf\_atual) / bf\_inicial) \* 100, 2\) AS reducao\_percentual,

  RANK() OVER (ORDER BY (bf\_inicial \- bf\_atual) DESC) AS ranking\_evolucao

FROM evolucao;

### Taxa de variação por dobra (evolução localizada de gordura)

SELECT

  a.aluno\_id,

  a.data\_avaliacao,

  d.abdominal\_mm,

  LAG(d.abdominal\_mm) OVER (PARTITION BY a.aluno\_id ORDER BY a.data\_avaliacao) AS abdominal\_anterior,

  ROUND(

    (d.abdominal\_mm \- LAG(d.abdominal\_mm) OVER (PARTITION BY a.aluno\_id ORDER BY a.data\_avaliacao))

    / LAG(d.abdominal\_mm) OVER (PARTITION BY a.aluno\_id ORDER BY a.data\_avaliacao) \* 100

  , 2\) AS variacao\_pct\_abdominal

FROM avaliacao a

JOIN avaliacao\_dobras d ON d.avaliacao\_id \= a.id;

### Evolução de circunferências por aluno (delta em cm)

SELECT

  a.aluno\_id,

  a.data\_avaliacao,

  c.cintura\_cm,

  c.quadril\_cm,

  c.coxa\_cm,

  LAG(c.cintura\_cm) OVER (PARTITION BY a.aluno\_id ORDER BY a.data\_avaliacao) AS cintura\_anterior,

  c.cintura\_cm \- LAG(c.cintura\_cm) OVER (PARTITION BY a.aluno\_id ORDER BY a.data\_avaliacao) AS delta\_cintura\_cm

FROM avaliacao a

JOIN avaliacao\_circunferencias c ON c.avaliacao\_id \= a.id;

### Treinos por grupo muscular mais trabalhado por aluno

SELECT

  a.id AS aluno\_id,

  u.nome,

  e.grupo\_muscular,

  COUNT(it.id) AS total\_exercicios

FROM aluno a

JOIN usuario u ON a.usuario\_id \= u.id

JOIN treino t ON t.aluno\_id \= a.id

JOIN item\_treino it ON it.treino\_id \= t.id

JOIN exercicio e ON e.id \= it.exercicio\_id

GROUP BY a.id, u.nome, e.grupo\_muscular

ORDER BY a.id, total\_exercicios DESC;

---

## 7\. Motor de Cálculo do Backend (assessments)

### Fórmulas — Jackson & Pollock 7 Dobras \+ Siri

Σ7DC \= soma das 7 dobras em mm

Homens:  DC \= 1.112 \- (0.00043499 \* Σ7DC) \+ (0.00000055 \* Σ7DC²) \- (0.00028826 \* idade)

Mulheres: DC \= 1.0970 \- (0.00046971 \* Σ7DC) \+ (0.00000056 \* Σ7DC²) \- (0.00012828 \* idade)

%G (Siri) \= (4.95 / DC \- 4.50) \* 100

Massa Gorda (kg) \= peso\_kg \* (%G / 100\)

Massa Magra (kg) \= peso\_kg \- Massa Gorda

RCQ \= cintura\_cm / quadril\_cm

### Classificação RCQ (OMS)

| Sexo | Baixo Risco | Risco Moderado | Risco Alto |
| :---- | :---- | :---- | :---- |
| Masculino | \< 0.90 | 0.90 – 0.99 | ≥ 1.00 |
| Feminino | \< 0.80 | 0.80 – 0.84 | ≥ 0.85 |

### Fluxo de processamento

O endpoint `POST /api/assessments/avaliacoes/` recebe o payload completo, calcula e persiste os resultados no backend. Celery fica como opção futura se o cálculo crescer ou passar a exigir processamento assíncrono.

1. Receber: `peso_kg`, `altura_cm`, 7 dobras (mm), 10 circunferências (cm)  
2. Buscar: `sexo` e `data_nascimento` do aluno → calcular idade em anos completos  
3. Calcular: Σ7DC \= soma das 7 dobras  
4. Calcular: DC via equação J\&P conforme sexo  
5. Calcular: %G via Siri  
6. Calcular: Massa Gorda, Massa Magra, RCQ  
7. Persistir atomicamente: `avaliacao` (campos calculados) \+ `avaliacao_dobras` \+ `avaliacao_circunferencias`

**Usar `transaction.atomic()` no caso de uso** — se qualquer uma das 3 persistências falhar, nenhuma é salva.

### Taxa de variação entre avaliações

variacao\_pct \= ((valor\_atual \- valor\_anterior) / valor\_anterior) \* 100

Negativo \= redução. Positivo \= ganho.

---

## 8\. Arquitetura de Implementação

### 8.1 Estrutura de diretórios do backend Django

backend/

├── config/

│   ├── \_\_init\_\_.py

│   ├── settings.py        → lê tudo de variáveis de ambiente via django-environ

│   ├── urls.py            → inclui urls de cada app

│   ├── asgi.py            → aplicação ASGI HTTP (WS futuro)

│   ├── wsgi.py

├── apps/

│   ├── core/

│   │   ├── middleware.py

│   │   ├── mixins.py

│   │   ├── exceptions.py

│   │   └── logging\_utils.py

│   ├── accounts/          → usuario, aluno e autenticação JWT

│   │   ├── models.py      → Usuario (AbstractBaseUser), Aluno

│   │   ├── serializers.py

│   │   ├── views.py

│   │   ├── urls.py

│   │   └── permissions.py  → permissões de domínio (ex: IsPersonal)

│   ├── workouts/          → padrão CRUD simples

│   │   ├── models.py      → Exercicio, Treino, ItemTreino

│   │   ├── serializers.py

│   │   ├── views.py

│   │   └── urls.py

│   └── assessments/       → padrão avançado (regra de negócio complexa)

│       ├── api/

│       │   ├── serializers.py

│       │   ├── views.py

│       │   └── urls.py

│       ├── application/

│       │   ├── use\_cases.py   → orquestra o fluxo de criação da avaliação

│       │   └── calculadora.py → funções puras de J\&P e Siri

│       └── models.py

├── pyproject.toml

├── poetry.lock

├── Procfile

├── Dockerfile

└── .env.example

### 8.2 Estrutura de diretórios do frontend Next.js

frontend/

├── src/

│   ├── app/

│   │   ├── (auth)/

│   │   │   └── login/page.tsx

│   │   ├── dashboard/page.tsx          → listagem de alunos do personal

│   │   ├── alunos/

│   │   │   └── \[id\]/

│   │   │       ├── page.tsx            → perfil do aluno

│   │   │       ├── treinos/page.tsx    → fichas de treino

│   │   │       ├── avaliacoes/page.tsx → histórico de avaliações

│   │   │       └── evolucao/page.tsx   → gráficos de evolução

│   │   └── layout.tsx

│   ├── components/

│   │   ├── global/                     → Navbar, Sidebar, Layout

│   │   └── features/

│   │       ├── workouts/               → FichaCard, ExercicioList, ItemTreinoForm

│   │       └── assessments/            → AvaliacaoForm, EvolucaoChart, RCQBadge

│   ├── lib/

│   │   ├── apiClient.ts                → Axios com interceptors (JWT, CSRF)

│   │   └── apiService.ts              → funções agrupadas por módulo

│   ├── types/

│   │   ├── api/                        → tipos de request/response da API

│   │   └── entities/                   → Usuario, Aluno, Treino, Avaliacao...

│   └── utils/mappers/                  → transforma response da API em entidade tipada

├── next.config.mjs                     → rewrite /api/\* → backend

├── .env.local.example

├── package.json

└── Dockerfile

### 8.3 Configurações essenciais do Django (`settings.py`)

\# Banco de dados

DATABASES \= {

    "default": {

        "ENGINE": env("DB\_ENGINE", default="django.db.backends.postgresql"),

        "NAME": env("DB\_NAME"),

        "USER": env("DB\_USER"),

        "PASSWORD": env("DB\_PASSWORD"),

        "HOST": env("DB\_HOST", default="localhost"),

        "PORT": env("DB\_PORT", default="5432"),

    }

}

\# Auth

AUTH\_USER\_MODEL \= "accounts.Usuario"

AUTH\_COOKIE\_REFRESH\_NAME \= "refresh\_token"

AUTH\_COOKIE\_SECURE \= env.bool("AUTH\_COOKIE\_SECURE", default=False)

AUTH\_COOKIE\_SAMESITE \= env("AUTH\_COOKIE\_SAMESITE", default="Lax")

SIMPLE\_JWT \= {

    "ACCESS\_TOKEN\_LIFETIME": timedelta(minutes=15),

    "REFRESH\_TOKEN\_LIFETIME": timedelta(days=7),

    "ROTATE\_REFRESH\_TOKENS": True,

    "BLACKLIST\_AFTER\_ROTATION": True,

    "AUTH\_HEADER\_TYPES": ("Bearer",),

}

\# Email dev

EMAIL\_BACKEND \= env("EMAIL\_BACKEND", default="django.core.mail.backends.console.EmailBackend")

DEFAULT\_FROM\_EMAIL \= env("DEFAULT\_FROM\_EMAIL", default="no-reply@fitsync.local")

### 8.4 Procfile (desenvolvimento local com Honcho)

web: daphne \-b 0.0.0.0 \-p ${PORT:-8000} config.asgi:application

### 8.5 Serviços e portas

| Serviço | Porta | Responsabilidade |
| :---- | :---- | :---- |
| `frontend` | 3000 | Next.js App Router |
| `api` | 8000 | Django/DRF via Daphne/ASGI |
| `postgres` | 5432 | Banco relacional principal |

### 8.6 Rewrite do Next.js (`next.config.mjs`)

const apiProxyTarget \= (

  process.env.API\_PROXY\_TARGET ||

  process.env.NEXT\_PUBLIC\_API\_PROXY\_TARGET ||

  "http://localhost:8000"

).replace(/\\/api\\/?$/, "");

const nextConfig \= {

  async rewrites() {

    return \[{ source: "/api/:path\*", destination: \`${apiProxyTarget}/api/:path\*\` }\];

  },

};

export default nextConfig;

### 8.7 Variáveis de ambiente (`.env.example` — backend)

\# Django

DEBUG=True

SECRET\_KEY=change-me

ALLOWED\_HOSTS=localhost,127.0.0.1,0.0.0.0

\# Database

DB\_ENGINE=django.db.backends.postgresql

DB\_NAME=fitsync\_dev

DB\_USER=fitsync\_app

DB\_PASSWORD=change-me

DB\_HOST=localhost

DB\_PORT=5432

\# CORS

CORS\_ALLOWED\_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

CORS\_ALLOW\_CREDENTIALS=True

\# Auth cookies (dev)

AUTH\_COOKIE\_REFRESH\_NAME=refresh\_token

AUTH\_COOKIE\_SECURE=False

AUTH\_COOKIE\_SAMESITE=Lax

CSRF\_COOKIE\_SECURE=False

CSRF\_COOKIE\_SAMESITE=Lax

\# Email dev

EMAIL\_BACKEND=django.core.mail.backends.console.EmailBackend

DEFAULT\_FROM\_EMAIL=no-reply@fitsync.local

---

## 9\. Endpoints da API REST (planejamento)

### auth/accounts

| Método | Endpoint | Descrição |
| :---- | :---- | :---- |
| POST | `/api/auth/register/` | Cadastro público de `PERSONAL` ou `ALUNO`; nunca `ADMIN` |
| POST | `/api/auth/login/` | Login por email/senha — retorna access token no JSON e refresh em cookie HttpOnly |
| POST | `/api/auth/refresh/` | Renova access token usando refresh cookie |
| POST | `/api/auth/logout/` | Blacklista refresh token e limpa cookie |
| GET/PATCH | `/api/auth/me/` | Perfil do usuário autenticado, incluindo `tipo` |
| POST | `/api/auth/password-reset/` | Solicita redefinição de senha |
| POST | `/api/auth/password-reset/confirm/` | Confirma redefinição de senha |
| GET/POST | `/api/accounts/admin/usuarios/` | Admin lista/cria usuários com senha temporária |
| GET/PATCH | `/api/accounts/admin/usuarios/{id}/` | Admin consulta/edita usuário sem alterar `tipo` |
| POST | `/api/accounts/admin/usuarios/{id}/ativar/` | Admin ativa usuário |
| POST | `/api/accounts/admin/usuarios/{id}/desativar/` | Admin desativa usuário |
| GET | `/api/accounts/admin/personais/` | Admin lista personais |
| GET | `/api/accounts/admin/alunos/` | Admin lista alunos e vínculo com personal |
| GET | `/api/accounts/personal/alunos/` | Personal lista seus alunos |
| GET | `/api/accounts/personal/alunos/{id}/` | Personal vê perfil de aluno vinculado |
| GET/PATCH | `/api/accounts/aluno/me/` | Aluno vê/edita seu perfil estendido |

### workouts

| Método | Endpoint | Descrição |
| :---- | :---- | :---- |
| GET/POST | `/api/workouts/exercicios/` | Catálogo global de exercícios |
| GET/PATCH | `/api/workouts/exercicios/{id}/` | Detalhe do exercício |
| POST | `/api/workouts/exercicios/{id}/arquivar/` | Arquiva exercício |
| GET/POST | `/api/workouts/templates/` | Templates de treino do personal |
| GET/PATCH | `/api/workouts/templates/{id}/` | Detalhe do template |
| POST | `/api/workouts/templates/{id}/arquivar/` | Arquiva template |
| POST | `/api/workouts/templates/{id}/aplicar/` | Copia template para ficha de um aluno |
| GET/POST | `/api/workouts/treinos/` | Fichas de treino (filtrar por aluno via query param) |
| GET/PATCH | `/api/workouts/treinos/{id}/` | Detalhe da ficha |
| POST | `/api/workouts/treinos/{id}/ativar/` | Ativa ficha e desativa as demais do aluno |
| POST | `/api/workouts/treinos/{id}/arquivar/` | Arquiva ficha |

### assessments

| Método | Endpoint | Descrição |
| :---- | :---- | :---- |
| GET/POST | `/api/assessments/avaliacoes/` | Listar / criar avaliação escolhendo método |
| GET/PATCH | `/api/assessments/avaliacoes/{id}/` | Detalhe/correção com dados do método aninhados |
| POST | `/api/assessments/avaliacoes/{id}/arquivar/` | Arquiva avaliação |
| GET | `/api/assessments/alunos/{id}/evolucao/` | Dados para gráficos — usa window functions |
| GET | `/api/assessments/personal/ranking/` | Ranking de alunos por perda de BF |

---

## 10\. Sequência de Implementação

### Fase 1 — Fundação (nada de domínio antes disso estar verde)

- [x] Criar projeto Django com `config/` \+ `apps/core/`  
- [x] Configurar Poetry, travar `poetry.lock`, criar `.env.example`  
- [x] Subir PostgreSQL via Docker Compose  
- [x] Criar `Procfile`/`Makefile` → validar `make dev`  
- [x] Implementar `apps/accounts` — models `Usuario` \+ `Aluno` \+ migrations \+ JWT auth com refresh cookie HttpOnly  
- [x] Migrar `Usuario` de `is_personal` para `tipo` (`ADMIN`, `PERSONAL`, `ALUNO`)  
- [ ] Criar superuser, validar login e endpoint `/api/auth/me/`

### Fase 2 — API de domínio

- [x] Modelar `apps/workouts` — `Exercicio`, `TreinoTemplate`, `ItemTreinoTemplate`, `Treino`, `ItemTreino` com validação de ficha ativa  
- [x] Modelar `apps/assessments` — avaliação por método (`DOBRAS`, `BIOIMPEDANCIA`, `CIRCUNFERENCIAS`, `COMBINADO`)  
- [x] Implementar CRUD/API de `Exercicio`, `TreinoTemplate`, `ItemTreinoTemplate`, `Treino`, `ItemTreino`  
- [x] `assessments/application/calculadora.py` — funções puras J\&P \+ Siri com testes unitários  
- [x] Endpoint de avaliação: recebe payload → calcula → persiste com `transaction.atomic()`  
- [x] Views de relatório usando as queries da seção 6
- [x] Padronizar paginação, routers e arquivamento lógico da API de domínio

### Fase 3 — Frontend

- [ ] Criar projeto Next.js com TypeScript, configurar `apiClient.ts` com Axios  
- [ ] Tela de login → autenticação JWT  
- [ ] Dashboard do personal → listagem de alunos  
- [ ] CRUD de templates e fichas de treino  
- [ ] Formulário de avaliação física com seleção de método  
- [ ] Tela de evolução → gráficos de BF, massa magra e circunferências ao longo do tempo

### Fase 4 — Infraestrutura completa

- [ ] `Dockerfile` backend (Daphne/ASGI, multi-stage não necessário)  
- [ ] `Dockerfile` frontend (multi-stage, Node 20 Alpine)  
- [ ] `docker-compose.yml` completo com healthchecks em postgres e serviços futuros necessários  
- [ ] Validar bootstrap completo com `docker compose up --build`

---

## 11\. Histórico de Decisões

| Data | Decisão |
| :---- | :---- |
| 2026-05-24 | Modelagem inicial dos 3 módulos definida: accounts, workouts, assessments |
| 2026-05-24 | Optado por tabela única `usuario` com flag `is_personal` em vez de tabelas separadas |
| 2026-05-24 | Campo `repeticoes` em `item_treino` definido como String para suportar "Falha" e faixas |
| 2026-05-24 | Módulo `assessments` reestruturado: `avaliacao` desmembrada em 3 tabelas |
| 2026-05-24 | Adotado protocolo Jackson & Pollock 7 dobras \+ equação de Siri como padrão de cálculo de BF |
| 2026-05-24 | `percentual_gordura` passa a ser campo calculado pelo backend, não input manual |
| 2026-05-24 | Campo `sexo` adicionado à tabela `aluno` — obrigatório para equação correta de DC |
| 2026-05-24 | RCQ adicionado como indicador de risco cardiovascular com classificação OMS |
| 2026-05-24 | Campos calculados persistidos na `avaliacao` para garantir histórico imutável |
| 2026-05-24 | Stack inicial planejada: Django 5 \+ DRF \+ Daphne/ASGI \+ PostgreSQL 16 \+ Redis \+ Celery \+ Next.js |
| 2026-05-25 | Stack real da fundação ajustada para Django 6 \+ DRF \+ Daphne/ASGI \+ PostgreSQL 16 local via Docker; Redis/Celery ficam para etapa futura |
| 2026-05-25 | Auth usa `/api/auth/*`; access token volta no JSON e refresh token fica em cookie HttpOnly |
| 2026-05-25 | Cadastro público pode criar personal ou aluno; aluno exige `personal_id` de usuário personal ativo |
| 2026-05-26 | Perfis de produto passam a ser `Usuario.tipo` com `ADMIN`, `PERSONAL` e `ALUNO`; o login retorna `tipo` para o frontend escolher a interface |
| 2026-05-26 | Medidas corporais, dobras e bioimpedância ficam no histórico de avaliações, não no cadastro do aluno |
| 2026-05-26 | Treinos passam a suportar templates reutilizáveis; aplicar template copia itens para uma ficha independente do aluno |
| 2026-05-26 | API MVP de domínio usa ViewSets/routers, paginação DRF, payloads aninhados e arquivamento lógico com `ativo` |
| 2026-05-25 | Banco local deve nascer com `AUTH_USER_MODEL = "accounts.Usuario"` antes das migrations limpas |
| 2026-05-24 | Motor de cálculo BF planejado com transaction.atomic(); execução assíncrona via Celery fica postergada |
| 2026-05-24 | `assessments` adota padrão avançado (api/ \+ application/ \+ models) por ter regra de negócio complexa |
| 2026-05-24 | `accounts` e `workouts` adotam padrão CRUD simples (models \+ serializers \+ views \+ urls) |
| 2026-05-24 | UUIDs como PKs em todas as tabelas (melhor para APIs REST e privacidade) |
| 2026-05-24 | Campos Decimal com precisão explícita definida (ex: Decimal(5,2)) para todos os campos de medida |
| 2026-05-24 | Sem WebSocket na fase inicial — ASGI mantido desde o início para facilitar adição futura |
| 2026-05-24 | Honcho/Procfile mantido para API; Makefile orquestra PostgreSQL local, migrations e Daphne |

---

**Instrução para o agente:** Sempre que uma nova feature, tabela, endpoint ou decisão for tomada, registre no item 11 (Histórico de Decisões) e atualize as seções relevantes deste documento antes de gerar qualquer código ou artefato.  
