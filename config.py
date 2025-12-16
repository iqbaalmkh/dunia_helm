import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost/dunia_helm"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

LEAD_TIME_DAYS = 4
WORKING_DAYS = 30
ORDER_COST = 50000
HOLDING_RATE = 0.1