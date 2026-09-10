"""Linux PTY check of the real app.py console; writes an unedited terminal transcript."""
import os, pty, select, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    target=ROOT/'evidence'/'console.txt'
    target.parent.mkdir(exist_ok=True)
    env={**os.environ,'RUNTIME_DIR':str(ROOT/'runtime'/f'cli_{time.time_ns()}'),'BACKEND':'local','TOP_K':'3','PYTHONUNBUFFERED':'1'}
    master,slave=pty.openpty()
    child=subprocess.Popen([sys.executable,'app.py'],cwd=ROOT,env=env,stdin=slave,stdout=slave,stderr=slave,close_fds=True)
    os.close(slave)
    output=bytearray()
    pending=bytearray()
    def receive(until_prompt=True):
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            if until_prompt and pending.endswith('Вы: '.encode()):
                pending.clear();return
            if select.select([master],[],[],0.2)[0]:
                try:part=os.read(master,65536)
                except OSError:part=b''
                if not part:return
                output.extend(part);pending.extend(part)
            elif child.poll() is not None:return
        raise TimeoutError('Console did not become ready')
    try:
        receive()
        for command in ['/help','','/unknown','/top_k 0','/source missing.txt','/sources','Что такое RAG?','Что такое RAG?','/stats','/top_k 7','/source python.txt','Кто создал Python и в каком году?','/source all','/reindex','/clear_cache','/stats','/exit']:
            os.write(master,(command+'\n').encode())
            receive(until_prompt=command!='/exit')
        child.wait(timeout=15)
        text=output.decode('utf-8').replace('\r\n','\n')
        target.write_text(text,encoding='utf-8')
        assert child.returncode==0
        for expected in ['Кэш: найден','1991','TOP_K=7','Кэш очищен.','База не изменилась.','Неизвестная команда.','Нет такого источника','До свидания!']:
            assert expected in text,expected
        eof=subprocess.run([sys.executable,'app.py'],cwd=ROOT,env=env,input='',text=True,capture_output=True,timeout=30)
        (target.parent/'console_eof.txt').write_text(eof.stdout+eof.stderr,encoding='utf-8')
        assert eof.returncode==0 and eof.stdout.count('До свидания!')==1
        print('CLI and EOF: PASS')
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=15)
        os.close(master)

if __name__=='__main__':main()
