from flask import Flask
from offline_latex_generator.config import config
from offline_latex_generator.utils.logger import logger

def create_app() -> Flask:
    """Application factory for Offline LaTeX Generator."""
    app = Flask(__name__)
    
    # Configure Flask app defaults
    app.config["MAX_CONTENT_LENGTH"] = config.get("server.max_upload_size_mb") * 1024 * 1024
    
    # Register blueprints or endpoints here in later phases
    @app.route("/health")
    def health():
        return {"status": "healthy", "env": config.env}

    logger.info(f"Offline LaTeX Generator app created in '{config.env}' mode")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host=config.get("server.host", "0.0.0.0"),
        port=config.get("server.port", 5000)
    )
