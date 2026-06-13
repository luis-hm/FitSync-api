# Metas do FitSync para o trabalho de Banco de Dados

Este arquivo guarda o que ainda falta organizar para entregar o FitSync como trabalho final de Banco de Dados, sem deixar a parte de produto esconder o que o professor quer avaliar.

## Objetivo da entrega

Apresentar o FitSync como um sistema de academia com foco em:

- modelagem conceitual;
- modelagem logica;
- estrutura de tabelas;
- relacionamentos;
- CRUD web;
- comandos SQL/ORM;
- relatorios gerados a partir dos dados armazenados.

## Escopo recomendado para apresentar

Nao tentar apresentar o sistema inteiro. Focar no recorte principal:

- usuarios;
- personais;
- alunos;
- categorias de exercicio;
- exercicios;
- treinos;
- itens de treino;
- avaliacoes fisicas.

Partes como JWT, reset de senha, CORS, OpenAPI, importacao wger e arquitetura de producao sao extras. Citar apenas se sobrar tempo.

## Checklist principal

- [ ] Criar DER conceitual.
- [ ] Criar modelo logico no MySQL Workbench, brModelo ou ferramenta semelhante.
- [ ] Criar script SQL com DDL.
- [ ] Criar script SQL com DML.
- [ ] Criar pelo menos 3 consultas de relatorio.
- [ ] Garantir que pelo menos 1 consulta de relatorio use JOIN.
- [ ] Preparar dados de exemplo para a apresentacao.
- [ ] Ensaiar demonstracao web criando, editando e arquivando um exercicio ou treino.
- [ ] Preparar um README academico curto com tema, integrantes, instrucoes e resumo das tabelas.

## DER conceitual

Entidades principais sugeridas:

- Usuario
- Personal
- Aluno
- CategoriaExercicio
- Exercicio
- Treino
- ItemTreino
- Avaliacao

Relacionamentos principais:

- um personal possui varios alunos;
- um aluno pertence a um personal;
- um aluno possui varios treinos;
- um treino possui varios itens de treino;
- um item de treino referencia um exercicio;
- um exercicio pertence a uma categoria;
- um aluno possui varias avaliacoes fisicas;
- uma avaliacao pertence a um aluno e a um personal.

## Modelo logico

O modelo logico deve mostrar:

- nomes das tabelas;
- atributos;
- chaves primarias;
- chaves estrangeiras;
- tipos de dados;
- cardinalidades;
- campos obrigatorios;
- campos unicos;
- tabelas associativas quando existirem.

Tabelas recomendadas para o modelo:

- `usuario`
- `personal_profile`
- `aluno`
- `categoria_exercicio`
- `exercicio`
- `treino`
- `item_treino`
- `avaliacao`
- `avaliacao_dobras`
- `avaliacao_bioimpedancia`
- `avaliacao_circunferencias`

## Scripts SQL

Arquivos sugeridos:

- `schema.sql`: criacao das tabelas.
- `dados_exemplo.sql`: inserts para popular o banco.
- `relatorios.sql`: consultas de relatorio.

O script DDL deve conter exemplos de:

- `CREATE TABLE`
- chaves primarias;
- chaves estrangeiras;
- `UNIQUE`;
- `NOT NULL`;
- tipos adequados para textos, datas, numeros e valores decimais.

O script DML deve conter exemplos de:

- `INSERT`;
- `SELECT`;
- `UPDATE`;
- `DELETE` ou explicacao de soft delete/arquivamento.

## Dados de exemplo

Criar uma base pequena, mas boa para demonstracao:

- 1 admin;
- 1 personal;
- 3 alunos;
- 5 categorias de exercicio;
- 10 exercicios;
- 2 treinos;
- 5 itens de treino;
- 3 avaliacoes por aluno.

Os dados precisam permitir que os relatorios mostrem resultados interessantes.

## Relatorios escolhidos

### 1. Evolucao fisica do aluno

Objetivo:

- mostrar a evolucao periodica do aluno usando avaliacoes fisicas.

Dados importantes:

- aluno;
- data da avaliacao;
- peso;
- percentual de gordura;
- massa gorda;
- massa magra;
- RCQ.

Tabelas envolvidas:

- `usuario`
- `aluno`
- `avaliacao`
- `avaliacao_circunferencias`

Esse deve ser o relatorio principal da apresentacao.

### 2. Ranking de evolucao dos alunos

Objetivo:

- mostrar quais alunos tiveram melhor evolucao em determinado periodo.

Possiveis metricas:

- maior reducao de percentual de gordura;
- maior reducao de peso;
- maior ganho de massa magra.

Tabelas envolvidas:

- `usuario`
- `aluno`
- `avaliacao`

Esse relatorio ajuda a mostrar agregacao, ordenacao e comparacao entre registros.

### 3. Treinos ativos por aluno com quantidade de exercicios

Objetivo:

- listar alunos, seus treinos ativos e a quantidade de exercicios em cada treino.

Tabelas envolvidas:

- `usuario`
- `aluno`
- `treino`
- `item_treino`
- `exercicio`

Esse relatorio e bom para demonstrar JOIN.

## Demonstracao web

Fluxo recomendado:

1. Fazer login no sistema.
2. Abrir a tela de exercicios ou treinos.
3. Criar um registro.
4. Editar o registro.
5. Arquivar o registro.
6. Mostrar uma listagem filtrada.
7. Mostrar um relatorio.
8. Explicar quais tabelas foram afetadas no banco.

Melhor demonstracao:

- criar, editar e arquivar um exercicio;
- ou criar, editar e arquivar um treino com itens.

## O que evitar na apresentacao

- Explicar detalhes demais de frontend.
- Gastar tempo com JWT, cookies e seguranca.
- Falar muito de produto, venda ou SaaS.
- Mostrar todos os modulos.
- Apresentar funcionalidades que nao ajudam na nota de Banco de Dados.

## Frase guia para a apresentacao

O FitSync e um sistema de academia que permite gerenciar alunos, personais, exercicios, treinos e avaliacoes fisicas. O foco do trabalho esta na modelagem das tabelas, nos relacionamentos, no CRUD web e nos relatorios gerados a partir dos dados armazenados.

