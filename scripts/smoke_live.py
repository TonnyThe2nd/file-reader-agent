"""Validação opcional com Ollama real, dados sintéticos e limpeza do workspace de teste."""
import argparse
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.core.database import SessionLocal
from app.core.security import current_owner
from app.main import app
from app.models import Conversation, Document, Interaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True, help='Confirma uso da API real e consumo de cota')
    parser.parse_args()
    owner = 'smoke-' + uuid4().hex
    app.dependency_overrides[current_owner] = lambda: owner
    try:
        with TestClient(app) as client:
            assert client.get('/ready').status_code == 200, 'Banco nao esta pronto'
            results = []
            for mode in ('direct', 'direct', 'rag'):
                response = client.post('/ask', data={'question':'Qual o total de pedidos?', 'mode':mode}, files={'file':('smoke.txt', b'O total de pedidos foi 42. A entrega ocorre em cinco dias.')})
                if response.status_code != 200:
                    print(f'{mode}: HTTP {response.status_code} - {response.json().get("detail", "Falha")}')
                    return 1
                result = response.json()
                assert '42' in result['answer'], 'Resposta nao contem o total esperado'
                results.append(result)
                print(f'{mode}: ok; cache={result["cache_hit"]}; fontes={len(result["sources"])}')
            assert results[1]['cache_hit']
            assert results[2]['sources']
            assert client.post('/feedback', json={'interaction_id':results[0]['interaction_id'], 'rating':1}).status_code == 200
            assert client.get('/stats').json()['total_interactions'] == 3
            assert len(client.get('/interactions').json()) == 3
            first = client.post('/ask', data={'question':'Qual o total de pedidos?', 'document_id':results[0]['document_id'], 'chat':'true'})
            assert first.status_code == 200, first.text
            cid = first.json()['conversation_id']
            followup = client.post('/ask', data={'question':'Esse total se refere a que?', 'conversation_id':cid})
            assert followup.status_code == 200, followup.text
            assert 'pedido' in followup.json()['answer'].lower()
            assert len(client.get('/conversations/'+cid).json()['messages']) == 2
            assert client.get('/documents/'+results[0]['document_id']+'/content').status_code == 200
            print('Chat com memoria, retomada e acesso ao documento validados.')
            print('Fluxo real completo validado.')
            return 0
    finally:
        app.dependency_overrides.pop(current_owner, None)
        with SessionLocal() as db:
            db.execute(delete(Interaction).where(Interaction.owner_id == owner))
            db.execute(delete(Conversation).where(Conversation.owner_id == owner))
            db.execute(delete(Document).where(Document.owner_id == owner))
            db.commit()


if __name__ == '__main__':
    raise SystemExit(main())
