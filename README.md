# FitSync API

API Django REST para a plataforma FitSync, voltada para gestao de personais, alunos, treinos, avaliacoes fisicas e acompanhamento de evolucao.

## Stack

- Python 3.12
- Django 6
- Django REST Framework
- SimpleJWT
- PostgreSQL 16
- Daphne/ASGI
- django-cors-headers
- drf-spectacular para OpenAPI, Swagger UI e Redoc
- Poetry para dependencias
- Docker Compose para PostgreSQL local

## Modulos

- `core`: raiz da API, health check, opcoes/enums e logging.
- `accounts`: usuarios, alunos, auth JWT, reset de senha e permissoes por papel.
- `workouts`: exercicios, templates de treino e treinos aplicados a alunos.
- `assessments`: avaliacoes fisicas, calculos corporais, evolucao e ranking.

## Setup Local

1. Instale as dependencias:

```bash
poetry install
```

2. Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

3. Suba o PostgreSQL:

```bash
make db
```

4. Rode as migracoes:

```bash
make migrate
```

5. Inicie a API:

```bash
make run
```

A API fica disponivel em:

```text
http://localhost:8000
```

## Comandos Uteis

```bash
make db
make migrate
make run
make dev
make check
make stop
```

Validacao completa:

```bash
poetry run python manage.py check
poetry run python manage.py spectacular --fail-on-warn
poetry run python manage.py test
```

## Variaveis De Ambiente

### Django

```env
DEBUG=True
SECRET_KEY=change-me
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
```

Em producao, use `DEBUG=False`, uma `SECRET_KEY` forte e `ALLOWED_HOSTS` restrito ao dominio real.

### Banco

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=fitsync_dev
DB_USER=fitsync_app
DB_PASSWORD=change-me
DB_HOST=localhost
DB_PORT=5432
```

### Frontend E CORS

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=True
FRONTEND_URL=http://localhost:3000
PASSWORD_RESET_FRONTEND_PATH=/reset-password
```

Para o frontend em Next.js:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Cookies

```env
AUTH_COOKIE_REFRESH_NAME=refresh_token
AUTH_COOKIE_SECURE=False
AUTH_COOKIE_SAMESITE=Lax
CSRF_COOKIE_SECURE=False
CSRF_COOKIE_SAMESITE=Lax
```

Em producao com front e API em dominios diferentes, normalmente use:

```env
AUTH_COOKIE_SECURE=True
AUTH_COOKIE_SAMESITE=None
CSRF_COOKIE_SECURE=True
CSRF_COOKIE_SAMESITE=None
```

### Email

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@fitsync.local
```

Em desenvolvimento, o reset de senha aparece no console. Em producao, configure um backend SMTP.

### JWT

```env
JWT_SIGNING_KEY=change-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7
```

## Documentacao Da API

- Swagger UI: `GET /api/docs/`
- Redoc: `GET /api/redoc/`
- Schema OpenAPI: `GET /api/schema/`

Swagger UI e util para devs testarem endpoints. Redoc e melhor para leitura e compartilhamento.

Para gerar tipos TypeScript no frontend:

```bash
npx openapi-typescript http://localhost:8000/api/schema/ -o src/types/api.ts
```

## Auth Para Frontend Next.js

O login retorna `access` no JSON e grava o refresh token em cookie HttpOnly.

### Login

```http
POST /api/auth/login/
Content-Type: application/json

{
  "email": "personal@example.com",
  "password": "StrongPass123!"
}
```

Resposta:

```json
{
  "access": "jwt-access-token",
  "user": {
    "id": "uuid",
    "nome": "Personal",
    "email": "personal@example.com",
    "tipo": "PERSONAL",
    "data_criacao": "2026-01-01T00:00:00Z"
  }
}
```

Use `credentials: "include"` para receber o cookie HttpOnly:

```ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

export async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error("Login failed");
  }

  return response.json() as Promise<{
    access: string;
    user: {
      id: string;
      nome: string;
      email: string;
      tipo: "ADMIN" | "PERSONAL" | "ALUNO";
      data_criacao: string;
    };
  }>;
}
```

### Requisicoes Autenticadas

Envie o access token no header:

```ts
await fetch(`${API_BASE_URL}/api/auth/me/`, {
  headers: {
    Authorization: `Bearer ${accessToken}`,
  },
  credentials: "include",
});
```

### Refresh

```http
POST /api/auth/refresh/
```

O backend le o refresh token do cookie HttpOnly. O frontend deve enviar:

```ts
await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
  method: "POST",
  credentials: "include",
});
```

Nunca salve o refresh token em `localStorage`.

### Logout

```ts
await fetch(`${API_BASE_URL}/api/auth/logout/`, {
  method: "POST",
  credentials: "include",
});
```

## Endpoints Principais

### Core

- `GET /api/`
- `GET /api/health/`
- `GET /api/options/`

`/api/options/` retorna enums para selects no frontend:

```json
{
  "auth": {
    "tipos_cadastro": [
      {"value": "PERSONAL", "label": "Personal"},
      {"value": "ALUNO", "label": "Aluno"}
    ]
  },
  "accounts": {
    "sexos": [
      {"value": "M", "label": "Masculino"},
      {"value": "F", "label": "Feminino"}
    ]
  },
  "workouts": {
    "dias_semana": [
      {"value": "SEGUNDA", "label": "Segunda-feira"}
    ]
  },
  "assessments": {
    "metodos": [
      {"value": "DOBRAS", "label": "Dobras"}
    ]
  }
}
```

### Auth

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `PATCH /api/auth/me/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset/confirm/`

### Accounts

- `GET /api/accounts/admin/personais/`
- `GET /api/accounts/admin/alunos/`
- `GET /api/accounts/admin/usuarios/`
- `POST /api/accounts/admin/usuarios/`
- `PATCH /api/accounts/admin/usuarios/{id}/`
- `POST /api/accounts/admin/usuarios/{id}/ativar/`
- `POST /api/accounts/admin/usuarios/{id}/desativar/`
- `GET /api/accounts/personal/alunos/`
- `GET /api/accounts/personal/alunos/{id}/`
- `GET /api/accounts/aluno/me/`
- `PATCH /api/accounts/aluno/me/`

### Workouts

- `GET /api/workouts/exercicios/`
- `POST /api/workouts/exercicios/`
- `PATCH /api/workouts/exercicios/{id}/`
- `POST /api/workouts/exercicios/{id}/arquivar/`
- `GET /api/workouts/templates/`
- `POST /api/workouts/templates/`
- `PATCH /api/workouts/templates/{id}/`
- `POST /api/workouts/templates/{id}/aplicar/`
- `POST /api/workouts/templates/{id}/arquivar/`
- `GET /api/workouts/treinos/`
- `POST /api/workouts/treinos/`
- `PATCH /api/workouts/treinos/{id}/`
- `POST /api/workouts/treinos/{id}/ativar/`
- `POST /api/workouts/treinos/{id}/arquivar/`

### Assessments

- `GET /api/assessments/avaliacoes/`
- `POST /api/assessments/avaliacoes/`
- `PATCH /api/assessments/avaliacoes/{id}/`
- `POST /api/assessments/avaliacoes/{id}/arquivar/`
- `GET /api/assessments/alunos/{id}/evolucao/`
- `GET /api/assessments/personal/ranking/`

## Paginacao

Listagens usam paginação do DRF:

```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": []
}
```

O tamanho padrao de pagina e `20`.

## Padrao De Erros

Erros de validacao retornam `400` com campos:

```json
{
  "email": ["Ja existe um usuario com este email."]
}
```

Erros de autenticacao retornam `401`. Erros de permissao retornam `403`.

## Throttling

Endpoints sensiveis possuem limite:

- login: `5/min`
- refresh: `10/min`
- password reset: `3/hour`

Ao exceder o limite, a API retorna `429 Too Many Requests`.

## Logs

Os logs usam o prefixo `[FITSYNC]`.

- `logs/app.log`: logs gerais e performance.
- `logs/security.log`: login invalido, usuario inativo, `401` e `403`.

Arquivos `.log` nao devem ser versionados.

## Checklist Para Comecar O Frontend

- Criar app Next.js com React, TypeScript e Tailwind.
- Definir `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
- Implementar client HTTP com `credentials: "include"`.
- Guardar `access` em memoria/estado seguro do app.
- Nunca guardar refresh token em `localStorage`.
- Usar `/api/options/` para selects.
- Usar `/api/docs/` para testar payloads.
- Gerar tipos com `openapi-typescript` se quiser contrato tipado.
