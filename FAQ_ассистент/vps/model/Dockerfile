FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir transformers==4.48.3 peft==0.14.0
ENV HF_HOME=/opt/weights HF_HUB_DISABLE_XET=1
RUN python -c "from huggingface_hub import list_repo_files,hf_hub_download; from transformers import AutoTokenizer; m='ai-forever/rugpt3small_based_on_gpt2'; rev='a9307e696cd3c5b7f953ff4cb19d76a4d81821d5'; files=list_repo_files(m,revision=rev); AutoTokenizer.from_pretrained(m,revision=rev); hf_hub_download(m,'config.json',revision=rev); hf_hub_download(m,'model.safetensors' if 'model.safetensors' in files else 'pytorch_model.bin',revision=rev)"
ENV HF_HUB_OFFLINE=1
COPY serve.py probe.py .
CMD ["python","-u","serve.py"]
