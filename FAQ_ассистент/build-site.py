from pathlib import Path
import json

src = Path("src")
out = Path("dist/server/index.js")
out.parent.mkdir(parents=True, exist_ok=True)
widget = (src/"widget.html").read_text()
assets = {name: json.loads((src/f"{name}.json").read_text()) for name in ("corpus","faq","topics","edge","prices")}
assets.update(widget=widget, widgetCode=(src/"widget.js").read_text(), css=(src/"style.css").read_text(),
              home=(src/"home.html").read_text().replace("</body>",widget+"</body>"))
out.write_text("".join(f"const {key} = {json.dumps(value, ensure_ascii=False)};\n" for key,value in assets.items())
               +(src/"faq-engine.mjs").read_text()+"\n"+(src/"service.mjs").read_text())
