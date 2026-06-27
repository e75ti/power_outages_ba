# settings.py

import os

class Config:
    DEBUG = False
    TESTING = False
    DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///default.db')
    NOTIFICATION_SERVICE_API_KEY = os.getenv('NOTIFICATION_SERVICE_API_KEY', '')
    GEOPY_API_KEY = os.getenv('GEOPY_API_KEY', '')

class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_URI = os.getenv('DEV_DATABASE_URI', 'sqlite:///dev.db')

class TestingConfig(Config):
    TESTING = True
    DATABASE_URI = os.getenv('TEST_DATABASE_URI', 'sqlite:///test.db')

class ProductionConfig(Config):
    DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///prod.db')