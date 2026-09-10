"""Semantic retrieval with source metadata and versioned, atomic index changes."""
from pathlib import Path
import hashlib, json, re
import chromadb
from chromadb.config import Settings
from local_embeddings import LocalE5Embeddings

def chunk_text(text, chunk_size=500, overlap=80):
    if chunk_size < 1 or not 0 <= overlap < chunk_size:
        raise ValueError('Нужно chunk_size > overlap >= 0')
    chunks, start = [], 0
    while start < len(text):
        end = min(start+chunk_size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = window.rfind('\n\n')
            if cut >= chunk_size//2:
                end = start+cut+2
            else:
                endings = [m.end() for m in re.finditer(r'[.!?]\s+',window) if m.end()>=chunk_size//2]
                if endings:
                    end = start+endings[-1]
                elif window.rfind(' ')>=chunk_size//2:
                    end = start+window.rfind(' ')+1
        value = text[start:end].strip()
        if value:
            chunks.append({'text':value, 'start':start, 'end':end})
        if end == len(text):
            break
        start = max(start+1,end-overlap)
    return chunks

class VectorStore:
    def __init__(self, config):
        self.config = config
        self.encoder = LocalE5Embeddings(config.models_dir/'e5')
        self.client = chromadb.PersistentClient(path=str(config.runtime_dir/'chroma'),
                                                settings=Settings(anonymized_telemetry=False))
        self.collection = None
        self.version = None
        self.source_names = []
        self.refresh()

    def prepare(self):
        root = self.config.data_dir.resolve()
        if not root.is_dir():
            raise ValueError('Папка data не найдена')
        files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {'.txt','.md'})
        if not files or len(files)>500:
            raise ValueError('Добавьте в data от 1 до 500 текстовых документов')
        records, hashes, names = [], [], []
        for path in files:
            if not path.resolve().is_relative_to(root):
                raise ValueError('Ссылка на файл вне папки data не поддерживается')
            if path.stat().st_size > 2_000_000:
                raise ValueError('Документ больше 2 МБ: '+path.name)
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            digest = hashlib.sha256(raw).hexdigest()
            hashes.append([path.name,digest])
            names.append(path.name)
            for i, part in enumerate(chunk_text(text,self.config.chunk_size,self.config.overlap),1):
                records.append({'id':hashlib.sha256(f'{path.name}:{digest}:{i}'.encode()).hexdigest(),
                                'text':part['text'], 'metadata':{'source':path.name,'chunk':i,
                                'start':part['start'],'end':part['end'],'sha256':digest}})
        if not records:
            raise ValueError('Документы пусты: индекс не изменён')
        version = hashlib.sha256(json.dumps([hashes,self.config.chunk_size,self.config.overlap,
                                            self.encoder.model,'E5-query-passage-mean-L2-v1'],
                                           ensure_ascii=False).encode()).hexdigest()
        return version, records, names

    def refresh(self):
        version, records, names = self.prepare()
        if version == self.version:
            return False
        name = 'rag_'+version[:24]
        collection = self.client.get_or_create_collection(name=name, embedding_function=None,
                    metadata={'hnsw:space':'cosine','version':version,'ready':False})
        ready = collection.metadata.get('ready',False) and collection.count()==len(records)
        if not ready:
            # Never change the active collection until the complete new index exists.
            try:
                for offset in range(0,len(records),64):
                    batch = records[offset:offset+64]
                    collection.upsert(ids=[r['id'] for r in batch], documents=[r['text'] for r in batch],
                                      metadatas=[r['metadata'] for r in batch],
                                      embeddings=self.encoder.embed_documents([r['text'] for r in batch]))
                if collection.count()!=len(records):
                    raise RuntimeError('Количество фрагментов индекса не совпало')
                # Chroma rejects hnsw:space in modify even if the value is unchanged.
                collection.modify(metadata={'version':version,'ready':True})
            except Exception:
                if self.collection is None or name != self.collection.name:
                    self.client.delete_collection(name)
                raise
        old_name = self.collection.name if self.collection is not None else None
        self.collection, self.version, self.source_names = collection, version, names
        # Only delete the immediately superseded collection after the new one is ready.
        if old_name is not None and old_name != name:
            self.client.delete_collection(old_name)
        return True

    def search(self, question, top_k=3, source=None):
        if not 1 <= top_k <= 10:
            raise ValueError('TOP_K должен быть от 1 до 10')
        if source is not None and source not in self.source_names:
            raise ValueError('Нет такого источника; используйте /sources')
        args = {'where':{'source':source}} if source else {}
        result = self.collection.query(query_embeddings=[self.encoder.embed_query(question)],
                    n_results=min(top_k,self.collection.count()),include=['documents','metadatas','distances'],**args)
        sources = []
        for i, text in enumerate(result['documents'][0]):
            meta = result['metadatas'][0][i]
            sources.append({'id':result['ids'][0][i], 'source':meta['source'],'chunk':meta['chunk'],
                            'text':text,'distance':float(result['distances'][0][i])})
        return sources
