# API Achados e Perdidos

API REST aberta para cadastrar objetos achados ou perdidos, filtrar por categoria e registrar solicitações de devolução.
Qualquer pessoa pode consumir os dados em JSON e montar o próprio app.

Feita só com Python 3 (biblioteca padrão) e SQLite. Nada para instalar.

## Como rodar

    python server.py          # porta 8080
    python server.py 3000     # outra porta

- **Documentação e testador:** http://localhost:8080 (página `index.html`, servida pela própria API)
- **Dados:** http://localhost:8080/api/itens

O banco `achados.db` é criado na primeira execução, já com 15 objetos de exemplo.
Para recomeçar do zero, apague o `achados.db`.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/itens?categoria=&status=&q=` | Lista objetos (filtros opcionais) |
| POST | `/api/itens` | Cadastra objeto |
| GET | `/api/itens/{id}` | Detalha objeto |
| PATCH | `/api/itens/{id}` | Altera `status` (`achado`, `perdido`, `devolvido`) |
| GET | `/api/devolucoes?status=&item_id=` | Lista solicitações |
| POST | `/api/devolucoes` | Registra solicitação de devolução |
| PATCH | `/api/devolucoes/{id}` | Altera `status` (`pendente`, `aprovada`, `recusada`) |
| GET | `/api/categorias` | Categorias e status aceitos |
| GET | `/api/health` | Verifica se a API está no ar |

Categorias válidas: `documentos`, `eletronicos`, `roupas`, `acessorios`, `chaves`, `bolsas_mochilas`, `outros`.

CORS liberado: dá para consumir direto do navegador, de qualquer site ou app.

## Exemplos

JavaScript:

    const itens = await (await fetch("http://localhost:8080/api/itens?categoria=chaves")).json();

Python:

    import requests
    print(requests.get("http://localhost:8080/api/itens", params={"q": "mochila"}).json())

curl:

    curl -X POST localhost:8080/api/devolucoes -H 'Content-Type: application/json' -d '{
      "item_id":1,"solicitante":"Ana","contato":"ana@email.com","mensagem":"A case tem um arranhão"}'

## Erros

Retornam JSON `{"erro": "..."}` com os códigos 404 (não encontrado), 409 (objeto já devolvido) e 422 (validação).