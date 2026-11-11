# Sistema de Achados e Perdidos

API + frontend para cadastrar objetos, filtrar por categoria e registrar solicitações de devolução.
Usa só Python 3 (biblioteca padrão) e SQLite. Nada para instalar.

## Como rodar

Coloque `server.py` e `index.html` na mesma pasta e execute:

    python3 server.py          # porta 8080
    python3 server.py 3000     # outra porta

Abra http://localhost:8080. O banco `achados.db` é criado na primeira execução, já com 15 objetos de exemplo.
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

Categorias válidas: `documentos`, `eletronicos`, `roupas`, `acessorios`, `chaves`, `bolsas_mochilas`, `outros`.

### Exemplos

    curl -X POST localhost:8080/api/itens -H 'Content-Type: application/json' -d '{
      "nome":"Guarda-chuva","descricao":"Preto","categoria":"outros",
      "status":"achado","local":"Recepção","data":"2026-11-09T13:25:00-03:00"}'

    curl -X POST localhost:8080/api/devolucoes -H 'Content-Type: application/json' -d '{
      "item_id":1,"solicitante":"Ana","contato":"ana@email.com","mensagem":"A case tem um arranhão"}'

Erros retornam JSON `{"erro": "..."}` com 404, 409 (objeto já devolvido), 422 (validação) etc.
