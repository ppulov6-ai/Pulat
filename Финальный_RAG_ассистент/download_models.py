"""Download pinned official model files, resume interrupted downloads, verify SHA256.

Run: python download_models.py
Only the Python standard library is required. Existing verified files are reused.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import time
import urllib.request

ROOT = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def download(item):
    target = ROOT / item['local_path']
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = item['expected_sha256']
    size = item['bytes']
    if target.exists():
        if target.stat().st_size == size and digest(target) == expected:
            print('Verified existing: ' + str(target.relative_to(ROOT)), flush=True)
            return
        raise RuntimeError('Existing final file failed verification: ' + str(target))
    temporary = target.with_suffix(target.suffix + '.part')
    url = ('https://huggingface.co/' + item['repo'] + '/resolve/'
           + item['revision'] + '/' + item['file'])
    for attempt in range(8):
        offset = temporary.stat().st_size if temporary.exists() else 0
        if offset == size:
            break
        if offset > size:
            raise RuntimeError('Partial file exceeds expected size: ' + str(temporary))
        headers = {'User-Agent': 'RAG-homework-model-downloader/1.0'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                if offset:
                    content_range = response.headers.get('Content-Range', '')
                    if response.status != 206 or not content_range.startswith(f'bytes {offset}-'):
                        raise RuntimeError('Server did not honor resume Range; partial file retained')
                with temporary.open('ab' if offset else 'wb') as stream:
                    downloaded = offset
                    reported = downloaded // (128 * 1024 * 1024)
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        stream.write(block)
                        downloaded += len(block)
                        if downloaded > size:
                            raise RuntimeError('Downloaded bytes exceed pinned size')
                        checkpoint = downloaded // (128 * 1024 * 1024)
                        if checkpoint > reported:
                            print(f'{target.name}: {downloaded}/{size} bytes', flush=True)
                            reported = checkpoint
            if temporary.stat().st_size == size:
                break
        except Exception as error:
            print(f'{target.name}: attempt {attempt + 1}: {error}', flush=True)
            if attempt == 7:
                raise
            time.sleep(min(2 ** attempt, 15))
    if not temporary.exists() or temporary.stat().st_size != size:
        raise RuntimeError('Incomplete download: ' + str(temporary))
    actual = digest(temporary)
    if actual != expected:
        raise RuntimeError('SHA256 mismatch: ' + str(temporary))
    temporary.replace(target)
    print(f'Verified: {target.relative_to(ROOT)} | {size} bytes | SHA256 {actual}', flush=True)


def main():
    manifest = json.loads((ROOT / 'model_manifest.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, manifest))
    print('All official model files verified.', flush=True)


if __name__ == '__main__':
    main()
