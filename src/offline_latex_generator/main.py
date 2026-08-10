from flask import Flask
from offline_latex_generator.config import config
from offline_latex_generator.utils.logger import logger
from offline_latex_generator.web.workspace_routes import workspace_bp

def create_app() -> Flask:
    """Application factory for Offline LaTeX Generator."""
    app = Flask(__name__)
    
    # Configure Flask app defaults
    app.config["MAX_CONTENT_LENGTH"] = config.get("server.max_upload_size_mb") * 1024 * 1024
    
    # Register blueprints
    app.register_blueprint(workspace_bp)
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return {"error": "File too large"}, 413
    
    @app.route("/health")
    def health():
        return {"status": "healthy", "env": config.env}

    logger.info(f"Offline LaTeX Generator app created in '{config.env}' mode")
    return app


if __name__ == "__main__":
    import sys
    import logging

    # Werkzeug writes its development WARNING banner to stderr by default.
    # On Windows, PowerShell treats any stderr output from a native command as a
    # NativeCommandError, which immediately kills the Python process. Redirect
    # Werkzeug's logger to stdout so all server output stays on a single stream.
    _werkzeug_logger = logging.getLogger("werkzeug")
    _werkzeug_logger.handlers.clear()
    _werkzeug_handler = logging.StreamHandler(sys.stdout)
    _werkzeug_handler.setFormatter(logging.Formatter("%(message)s"))
    _werkzeug_logger.addHandler(_werkzeug_handler)
    _werkzeug_logger.propagate = False

    app = create_app()
    app.run(
        host=config.get("server.host", "0.0.0.0"),
        port=config.get("server.port", 5000),
        debug=False,
        use_reloader=False,
    )
