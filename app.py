import os
from flask import Flask, jsonify, send_from_directory
from config import Config
from extensions import db, jwt, cache, cors
from auth_routes import auth_bp

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # Setup Cache with fallback if Redis is unavailable
    try:
        import redis
        r = redis.from_url(app.config.get('CACHE_REDIS_URL', 'redis://localhost:6379/0'))
        r.ping()
        cache.init_app(app, config={'CACHE_TYPE': 'RedisCache', 'CACHE_REDIS_URL': app.config['CACHE_REDIS_URL']})
        app.logger.info("Connected to Redis cache successfully.")
    except Exception as e:
        app.logger.warning(f"Redis not available ({e}). Falling back to SimpleCache.")
        cache.init_app(app, config={'CACHE_TYPE': 'SimpleCache'})

    # Register blueprints
    app.register_blueprint(auth_bp)

    # Lazily import and register remaining blueprints as they are created
    try:
        from admin_routes import admin_bp
        app.register_blueprint(admin_bp)
    except ImportError:
        pass

    try:
        from examiner_routes import examiner_bp
        app.register_blueprint(examiner_bp)
    except ImportError:
        pass

    try:
        from student_routes import student_bp
        app.register_blueprint(student_bp)
    except ImportError:
        pass

    try:
        from jobs_routes import jobs_bp
        app.register_blueprint(jobs_bp)
    except ImportError:
        pass

    try:
        from analytics_routes import analytics_bp
        app.register_blueprint(analytics_bp)
    except ImportError:
        pass

    try:
        from cache_routes import cache_bp
        app.register_blueprint(cache_bp)
    except ImportError:
        pass

    # Global JWT Error handlers
    @jwt.unauthorized_loader
    def unauthorized_response(callback):
        return jsonify({
            'success': False,
            'message': 'Missing Authorization Header. Please log in to proceed.'
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_response(callback):
        return jsonify({
            'success': False,
            'message': 'Invalid token. Signature verification failed.'
        }), 401

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({
            'success': False,
            'message': 'Session token has expired. Please log in again.'
        }), 401

    # Serve Single Page Application (Vue)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path):
        if path.startswith('api/'):
            return jsonify({'success': False, 'message': 'API endpoint not found.'}), 404
        static_dir = os.path.join(app.root_path, 'static')
        target_file = os.path.join(static_dir, path)
        if path != "" and os.path.exists(target_file):
            return send_from_directory(static_dir, path)
        else:
            index_path = os.path.join(static_dir, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_dir, 'index.html')
            return jsonify({
                'message': 'Examination Management Portal V2 API is live. Static frontend build not yet detected.'
            }), 200

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
