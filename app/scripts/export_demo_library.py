"""Gera ui/src/demo/library.fixture.json (temas da Biblioteca com o texto completo) e studio.fixture.json
(estudio de agentes do Lab), para o modo demo da
interface (npm run dev, ?demo) mostrar os artigos reais sem Python. So o servidor de desenvolvimento usa;
o build de producao nao inclui o arquivo.

    python app/scripts/export_demo_library.py
"""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from core import library  # noqa: E402

OUT = APP.parent / "ui" / "src" / "demo" / "library.fixture.json"
STUDIO = APP.parent / "ui" / "src" / "demo" / "studio.fixture.json"


def main() -> None:
    topics = []
    for t in library.catalog():
        full = library.topic(t["id"])
        full.pop("article", None)
        topics.append(full)
    OUT.write_text(json.dumps({"verified_on": library.VERIFIED_ON, "topics": topics}, ensure_ascii=False), encoding="utf-8")
    print(f"gravado {OUT.relative_to(APP.parent)} ({len(topics)} temas)")
    # Estudio de agentes do Lab: especificacao, memoria e codigo de cada agente (camada de fabrica)
    import tempfile
    from core import agent_studio
    from core.brain import Brain
    with tempfile.TemporaryDirectory() as tmp:
        brain = Brain(str(APP.parent / "vault"), personal_path=tmp)
        agents = {}
        for a in agent_studio.AGENTS:
            spec = agent_studio.spec(a, brain)
            agents[a] = {"spec": spec, "memory": agent_studio.memory(a, brain),
                         "sources": {f["path"]: agent_studio.source(a, f["path"])["text"] for f in spec["files"]}}
        brain.store.close()
    STUDIO.write_text(json.dumps(agents, ensure_ascii=False), encoding="utf-8")
    print(f"gravado {STUDIO.relative_to(APP.parent)} ({len(agents)} agentes)")


if __name__ == "__main__":
    main()
