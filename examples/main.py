"""Tooli Lab: Central entrypoint for all demo applications."""

from __future__ import annotations

from examples.artifactcatalog.app import app as artifactcatalog_app
from examples.configmigrate.app import app as configmigrate_app
from examples.datawrangler.app import app as datawrangler_app
from examples.envdoctor.app import app as envdoctor_app
from examples.logslicer.app import app as logslicer_app
from examples.mediameta.app import app as mediameta_app
from examples.patchpilot.app import app as patchpilot_app

# Import all sub-apps
from examples.repolens.app import app as repolens_app
from examples.secretscout.app import app as secretscout_app
from tooli import Tooli

app = Tooli(
    name="tooli-lab",
    help="A suite of CLI tools showcasing Tooli's agent-native superpowers.",
    version="0.1.0",
)

# Add sub-apps as command groups
app.add_typer(repolens_app, name="repolens")
app.add_typer(patchpilot_app, name="patchpilot")
app.add_typer(logslicer_app, name="logslicer")
app.add_typer(datawrangler_app, name="datawrangler")
app.add_typer(secretscout_app, name="secretscout")
app.add_typer(envdoctor_app, name="envdoctor")
app.add_typer(mediameta_app, name="mediameta")
app.add_typer(configmigrate_app, name="configmigrate")
app.add_typer(artifactcatalog_app, name="artifactcatalog")

if __name__ == "__main__":
    app()
